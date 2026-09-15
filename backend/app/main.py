import requests
from fastapi import FastAPI, HTTPException

from app.services.advanced_stats import get_matchup_advanced_metrics_safe
from app.services.analysis import calcola_analisi
from app.services.analysis_cache import (
    build_analysis_cache_key,
    load_cached_analysis,
    save_cached_analysis,
)
from app.services.competitions import (
    DEFAULT_COMPETITION,
    get_competition_config,
    list_competitions,
)
from app.services.football_api import (
    get_competition_teams,
    get_team_last_matches,
    stessa_squadra,
    trasforma_partite_squadra,
)
from app.services.shot_extras import get_matchup_shot_extras_safe
from app.services.team_data import (
    calcola_medie_casa_trasferta,
    crea_dati_squadra,
)
from app.services.understat_fallback import get_understat_recent_form
from app.services.upcoming_fixtures import get_upcoming_fixtures

app = FastAPI(
    title="Football AI",
    version="0.7.0",
    description="Motore di analisi statistica e probabilistica delle partite di calcio.",
)


def _provider_http_exception(exc):
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)

    if status_code == 429:
        return HTTPException(
            status_code=503,
            detail=(
                "Le fonti gratuite sono temporaneamente limitate e non e' "
                "disponibile nemmeno un fallback utilizzabile. Riprova tra poco."
            ),
        )

    return HTTPException(
        status_code=502,
        detail=(
            "La fonte dati principale e temporaneamente non disponibile. "
            "Riprova tra poco."
        ),
    )


@app.get("/")
def root():
    return {
        "app": "Football AI",
        "status": "online",
        "version": "0.7.0",
        "engine": "statistical-probabilistic",
        "multi_league": True,
    }


@app.get("/health")
def health():
    return {"status": "healthy", "version": "0.7.0"}


@app.get("/competitions")
def competitions():
    return {
        "status": "success",
        "competizioni": list_competitions(),
    }


@app.get("/competitions/{competizione}/teams")
def competition_teams(competizione: str):
    try:
        config = get_competition_config(competizione)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    try:
        squadre = get_competition_teams(config["slug"])
    except requests.RequestException as exc:
        raise _provider_http_exception(exc) from exc

    return {
        "status": "success",
        "competizione": {
            "slug": config["slug"],
            "name": config["name"],
        },
        "squadre": squadre,
    }


@app.get("/competitions/{competizione}/fixtures/upcoming")
def competition_upcoming_fixtures(
    competizione: str,
    limit: int = 20,
):
    try:
        config = get_competition_config(competizione)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    if limit < 1 or limit > 50:
        raise HTTPException(
            status_code=400,
            detail="Il limite deve essere compreso tra 1 e 50.",
        )

    try:
        partite = get_upcoming_fixtures(config["slug"], limit=limit)
    except requests.RequestException as exc:
        raise _provider_http_exception(exc) from exc

    return {
        "status": "success",
        "competizione": {
            "slug": config["slug"],
            "name": config["name"],
            "country": config["country"],
        },
        "partite": partite,
        "fallback_attivo": bool(
            partite and partite[0].get("data_fallback")
        ),
    }


@app.get("/analyze")
def analyze(
    casa: str = "",
    ospite: str = "",
    competizione: str = DEFAULT_COMPETITION,
    refresh: bool = False,
):
    casa = casa.strip()
    ospite = ospite.strip()

    try:
        config = get_competition_config(competizione)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    if not casa or not ospite:
        raise HTTPException(
            status_code=400,
            detail="Inserisci sia la squadra di casa sia la squadra ospite.",
        )

    if stessa_squadra(casa, ospite):
        raise HTTPException(
            status_code=400,
            detail="Le due squadre devono essere diverse.",
        )

    cache_key = build_analysis_cache_key(
        config["slug"],
        casa,
        ospite,
    )

    if not refresh:
        cached = load_cached_analysis(cache_key)
        if cached is not None:
            response = cached["response"]
            response["cache_analisi"] = {
                "salvata": True,
                "hit": True,
                "saved_at": cached.get("saved_at"),
                "aggiornamento_forzato": False,
                "richieste_fonti_evitabili": True,
            }
            return response

    provider_fallback_used = False

    try:
        partite_casa = get_team_last_matches(
            casa,
            config["slug"],
        )
        partite_ospite = get_team_last_matches(
            ospite,
            config["slug"],
        )

        ultime_partite_casa = trasforma_partite_squadra(
            partite_casa,
            casa,
        )
        ultime_partite_ospite = trasforma_partite_squadra(
            partite_ospite,
            ospite,
        )
    except requests.RequestException as provider_exc:
        # Il modello xG e le metriche avanzate usano gia' Understat. Se il
        # provider gratuito blocca le fixture con 429, manteniamo operativa
        # l'analisi usando Understat anche per la forma recente. I campi non
        # disponibili (corner, cartellini, possesso, attacchi) restano n/d.
        try:
            ultime_partite_casa = get_understat_recent_form(
                casa,
                config["slug"],
                limit=5,
            )
            ultime_partite_ospite = get_understat_recent_form(
                ospite,
                config["slug"],
                limit=5,
            )
            provider_fallback_used = True
        except requests.RequestException:
            raise _provider_http_exception(provider_exc) from provider_exc

    if not ultime_partite_casa:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Nessuna partita recente trovata per {casa} "
                f"in {config['name']}."
            ),
        )

    if not ultime_partite_ospite:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Nessuna partita recente trovata per {ospite} "
                f"in {config['name']}."
            ),
        )

    medie_casa = calcola_medie_casa_trasferta(
        ultime_partite_casa,
        "casa",
    )
    medie_ospite = calcola_medie_casa_trasferta(
        ultime_partite_ospite,
        "trasferta",
    )

    dati_casa = crea_dati_squadra(
        casa,
        ultime_partite_casa,
        medie_casa["gol_fatti"],
        medie_casa["gol_subiti"],
        medie_casa["corner"],
        medie_casa["ammonizioni"],
        medie_casa["possesso"],
        medie_casa["tiri_in_porta"],
        medie_casa["tiri_fuori"],
        medie_casa["attacchi"],
        medie_casa["attacchi_pericolosi"],
    )

    dati_ospite = crea_dati_squadra(
        ospite,
        ultime_partite_ospite,
        medie_ospite["gol_fatti"],
        medie_ospite["gol_subiti"],
        medie_ospite["corner"],
        medie_ospite["ammonizioni"],
        medie_ospite["possesso"],
        medie_ospite["tiri_in_porta"],
        medie_ospite["tiri_fuori"],
        medie_ospite["attacchi"],
        medie_ospite["attacchi_pericolosi"],
    )

    risultato = calcola_analisi(
        dati_casa,
        dati_ospite,
        config["slug"],
    )

    # I valori tecnici zero usati per mantenere compatibile il motore non
    # vengono mai presentati come osservazioni reali se non esiste un campione.
    if medie_casa.get("corner_campioni", 0) <= 0:
        risultato["corner_casa"] = None
    if medie_ospite.get("corner_campioni", 0) <= 0:
        risultato["corner_ospite"] = None
    if medie_casa.get("ammonizioni_campioni", 0) <= 0:
        risultato["ammonizioni_casa"] = None
    if medie_ospite.get("ammonizioni_campioni", 0) <= 0:
        risultato["ammonizioni_ospite"] = None

    volume = risultato.get("volume_tiri", {})
    campioni_volume_casa = min(
        medie_casa.get("tiri_in_porta_campioni", 0),
        medie_casa.get("tiri_fuori_campioni", 0),
    )
    campioni_volume_ospite = min(
        medie_ospite.get("tiri_in_porta_campioni", 0),
        medie_ospite.get("tiri_fuori_campioni", 0),
    )

    if campioni_volume_casa <= 0:
        volume["casa"] = None
    if campioni_volume_ospite <= 0:
        volume["ospite"] = None
    if volume.get("casa") is None or volume.get("ospite") is None:
        volume["differenziale"] = None

    risultato["volume_tiri"] = volume
    risultato["disponibilita_dati_gioco"] = {
        "casa": {
            "corner": medie_casa.get("corner_campioni", 0),
            "ammonizioni": medie_casa.get("ammonizioni_campioni", 0),
            "possesso": medie_casa.get("possesso_campioni", 0),
            "tiri": campioni_volume_casa,
            "attacchi": medie_casa.get("attacchi_campioni", 0),
            "attacchi_pericolosi": medie_casa.get(
                "attacchi_pericolosi_campioni",
                0,
            ),
        },
        "ospite": {
            "corner": medie_ospite.get("corner_campioni", 0),
            "ammonizioni": medie_ospite.get("ammonizioni_campioni", 0),
            "possesso": medie_ospite.get("possesso_campioni", 0),
            "tiri": campioni_volume_ospite,
            "attacchi": medie_ospite.get("attacchi_campioni", 0),
            "attacchi_pericolosi": medie_ospite.get(
                "attacchi_pericolosi_campioni",
                0,
            ),
        },
    }

    metriche_avanzate = get_matchup_advanced_metrics_safe(
        casa,
        ospite,
        config["slug"],
    )

    shot_extras = get_matchup_shot_extras_safe(
        casa,
        ospite,
        config["slug"],
        limit=5,
    )

    if (
        metriche_avanzate.get("status") == "success"
        and shot_extras.get("status") == "success"
    ):
        for side in ("home", "away"):
            if isinstance(metriche_avanzate.get(side), dict):
                metriche_avanzate[side] = {
                    **metriche_avanzate[side],
                    "shot_extras": shot_extras.get(side),
                }

        metriche_avanzate.setdefault("experimental", {})[
            "shot_extras"
        ] = "derived_recent_published"

    response = {
        "status": "success",
        "partita": f"{casa} vs {ospite}",
        "competizione": {
            "slug": config["slug"],
            "name": config["name"],
            "country": config["country"],
        },
        "modello": {
            "validato": config["model_validated"],
            "stato": (
                "validato"
                if config["model_validated"]
                else "sperimentale_in_validazione"
            ),
        },
        "fonti_dati": {
            "modello_xg": "Understat",
            "forma_recente": (
                "Understat_fallback"
                if provider_fallback_used
                else "5DollarFootballAPI"
            ),
            "provider_fallback_attivo": provider_fallback_used,
        },
        "analisi": risultato,
        "metriche_avanzate": metriche_avanzate,
        "ultime_partite": {
            "casa": ultime_partite_casa,
            "ospite": ultime_partite_ospite,
        },
    }

    saved_at = save_cached_analysis(cache_key, response)
    response["cache_analisi"] = {
        "salvata": saved_at is not None,
        "hit": False,
        "saved_at": saved_at,
        "aggiornamento_forzato": bool(refresh),
        "richieste_fonti_evitabili": False,
    }
    return response
