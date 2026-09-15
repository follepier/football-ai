from fastapi import FastAPI, HTTPException

from app.services.advanced_stats import get_matchup_advanced_metrics_safe
from app.services.analysis import calcola_analisi
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
from app.services.team_data import (
    calcola_medie_casa_trasferta,
    crea_dati_squadra,
)
from app.services.upcoming_fixtures import get_upcoming_fixtures

app = FastAPI(
    title="Football AI",
    version="0.7.0",
    description="Motore di analisi statistica e probabilistica delle partite di calcio.",
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

    return {
        "status": "success",
        "competizione": {
            "slug": config["slug"],
            "name": config["name"],
        },
        "squadre": get_competition_teams(config["slug"]),
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

    return {
        "status": "success",
        "competizione": {
            "slug": config["slug"],
            "name": config["name"],
            "country": config["country"],
        },
        "partite": get_upcoming_fixtures(config["slug"], limit=limit),
    }


@app.get("/analyze")
def analyze(
    casa: str = "",
    ospite: str = "",
    competizione: str = DEFAULT_COMPETITION,
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

    metriche_avanzate = get_matchup_advanced_metrics_safe(
        casa,
        ospite,
        config["slug"],
    )

    return {
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
        "analisi": risultato,
        "metriche_avanzate": metriche_avanzate,
        "ultime_partite": {
            "casa": ultime_partite_casa,
            "ospite": ultime_partite_ospite,
        },
    }
