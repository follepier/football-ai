import json
import os
import time
from datetime import datetime, timezone
from threading import Lock

import requests
from dotenv import load_dotenv

from app.services.competitions import (
    DEFAULT_COMPETITION,
    get_competition_config,
)

load_dotenv()

API_KEY = os.getenv("FOOTBALL_API_KEY")
BASE_URL = "https://api.5dollarfootballapi.com/v1"
SERIE_A_ID = 3405541143

# Cache tecnica per ridurre chiamate duplicate al provider gratuito.
# Le fixture cambiano lentamente, mentre le statistiche delle partite concluse
# sono sostanzialmente stabili: TTL piu' lunghi riducono drasticamente i 429.
FIXTURES_CACHE_TTL_SECONDS = 900
FIXTURES_STALE_TTL_SECONDS = 12 * 3600
FIXTURE_STATS_CACHE_TTL_SECONDS = 30 * 24 * 3600
FIXTURE_STATS_STALE_TTL_SECONDS = 365 * 24 * 3600
UNDERSTAT_CACHE_TTL_SECONDS = 300
PROVIDER_CACHE_DIR = os.getenv(
    "FOOTBALL_AI_PROVIDER_CACHE_DIR",
    "/tmp/football-ai-provider-cache",
)

# Le cache sono separate per competizione: questo evita che dati
# di campionati diversi possano contaminarsi tra loro.
_FIXTURES_CACHE = {}
_FIXTURE_STATS_CACHE = {}
_UNDERSTAT_CACHE = {}

_FIXTURES_CACHE_LOCK = Lock()
_FIXTURE_STATS_CACHE_LOCK = Lock()
_UNDERSTAT_CACHE_LOCK = Lock()


# ============================================================
# CACHE PROVIDER PERSISTENTE
# ============================================================


def _safe_cache_key(value):
    return "".join(
        char if char.isalnum() or char in ("-", "_") else "_"
        for char in str(value)
    )


def _provider_cache_path(kind, key):
    os.makedirs(PROVIDER_CACHE_DIR, exist_ok=True)
    return os.path.join(
        PROVIDER_CACHE_DIR,
        f"{kind}_{_safe_cache_key(key)}.json",
    )


def _build_cache_entry(value, ttl_seconds, stale_ttl_seconds, saved_at=None):
    saved_at = float(saved_at if saved_at is not None else time.time())
    return {
        "value": value,
        "saved_at": saved_at,
        "expires_at": saved_at + ttl_seconds,
        "stale_until": saved_at + stale_ttl_seconds,
    }


def _load_provider_disk_cache(kind, key, ttl_seconds, stale_ttl_seconds):
    path = _provider_cache_path(kind, key)

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        return None

    if not isinstance(payload, dict) or "value" not in payload:
        return None

    try:
        saved_at = float(payload.get("saved_at"))
    except (TypeError, ValueError):
        return None

    return _build_cache_entry(
        payload["value"],
        ttl_seconds,
        stale_ttl_seconds,
        saved_at=saved_at,
    )


def _save_provider_disk_cache(kind, key, value):
    path = _provider_cache_path(kind, key)
    temp_path = f"{path}.tmp"
    payload = {
        "saved_at": time.time(),
        "value": value,
    }

    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        os.replace(temp_path, path)
    except OSError:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass


def _stale_cache_value(cached, now):
    if cached is not None and now < cached.get("stale_until", 0):
        return cached.get("value")
    return None


# ============================================================
# MATCHING ROBUSTO NOMI SQUADRE
# ============================================================

TEAM_ALIASES = {
    # Serie A
    "inter": {
        "inter",
        "inter milan",
        "internazionale",
        "fc internazionale",
        "fc internazionale milano",
    },
    "ac milan": {
        "milan",
        "ac milan",
        "a c milan",
    },
    "parma calcio 1913": {
        "parma",
        "parma calcio 1913",
    },

    # Premier League
    "manchester city": {
        "manchester city",
        "man city",
    },
    "manchester united": {
        "manchester united",
        "man utd",
    },
    "newcastle united": {
        "newcastle united",
        "newcastle",
    },
    "nottingham forest": {
        "nottingham forest",
        "nottm forest",
    },

    # La Liga
    "alaves": {
        "alaves",
        "cd alaves",
    },
    "deportivo la coruna": {
        "deportivo la coruna",
        "deportivo a coruna",
    },

    # Bundesliga
    "bayern munich": {
        "bayern munich",
        "fc bayern munich",
        "bayern",
    },
    "fc cologne": {
        "fc cologne",
        "cologne",
    },
    "hamburger sv": {
        "hamburger sv",
        "hamburg",
    },
    "mainz 05": {
        "mainz 05",
        "mainz",
    },
    "rasenballsport leipzig": {
        "rasenballsport leipzig",
        "rb leipzig",
    },
    "freiburg": {
        "freiburg",
        "sc freiburg",
    },
    "schalke 04": {
        "schalke 04",
        "schalke",
    },
    "hoffenheim": {
        "hoffenheim",
        "tsg hoffenheim",
    },

    # Ligue 1
    "paris saint germain": {
        "paris saint germain",
        "paris saint-germain",
        "psg",
    },
}

# Se il provider restituisce due alias della stessa squadra, il frontend
# deve mostrare una sola voce stabile e leggibile.
PREFERRED_TEAM_DISPLAY_NAMES = {
    "deportivo la coruna": "Deportivo La Coruna",
}


def normalizza_nome_squadra(nome):
    nome = str(nome).strip().lower()

    for carattere in [".", "-", "_", "'"]:
        nome = nome.replace(carattere, " ")

    nome = " ".join(nome.split())

    for canonico, aliases in TEAM_ALIASES.items():
        if nome == canonico or nome in aliases:
            return canonico

    return nome


def stessa_squadra(nome_1, nome_2):
    return (
        normalizza_nome_squadra(nome_1)
        == normalizza_nome_squadra(nome_2)
    )


def _current_understat_season():
    now = datetime.now(timezone.utc)
    return now.year if now.month >= 7 else now.year - 1


def get_league_fixtures(competizione=DEFAULT_COMPETITION):
    config = get_competition_config(competizione)
    cache_key = config["slug"]
    now = time.time()

    with _FIXTURES_CACHE_LOCK:
        cached = _FIXTURES_CACHE.get(cache_key)

        if cached is None:
            cached = _load_provider_disk_cache(
                "fixtures",
                cache_key,
                FIXTURES_CACHE_TTL_SECONDS,
                FIXTURES_STALE_TTL_SECONDS,
            )
            if cached is not None:
                _FIXTURES_CACHE[cache_key] = cached

        if cached is not None and now < cached["expires_at"]:
            return cached["value"]

        stale_value = _stale_cache_value(cached, now)

        url = (
            f"{BASE_URL}/leagues/"
            f"{config['provider_league_id']}/fixtures"
        )

        headers = {
            "Authorization": f"Bearer {API_KEY}"
        }

        tutte_le_partite = []

        try:
            for pagina in range(1, 6):
                params = {
                    "page": pagina,
                    "per_page": 100,
                }

                response = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=15,
                )

                response.raise_for_status()

                dati = response.json()
                partite = dati.get("data", [])
                tutte_le_partite.extend(partite)

                if len(partite) < 100:
                    break
        except requests.RequestException:
            if stale_value is not None:
                return stale_value
            raise

        risultato = {
            "competition": config["slug"],
            "data": tutte_le_partite,
        }

        entry = _build_cache_entry(
            risultato,
            FIXTURES_CACHE_TTL_SECONDS,
            FIXTURES_STALE_TTL_SECONDS,
        )
        _FIXTURES_CACHE[cache_key] = entry
        _save_provider_disk_cache("fixtures", cache_key, risultato)

        return risultato


def get_serie_a_fixtures():
    # Wrapper compatibile con audit e test storici già esistenti.
    return get_league_fixtures("serie-a")


def get_competition_teams(competizione=DEFAULT_COMPETITION):
    partite = get_league_fixtures(competizione)["data"]

    # Deduplica per nome normalizzato, non per stringa grezza del provider.
    # Esempio reale: "Deportivo A Coruna" e "Deportivo La Coruna"
    # rappresentano la stessa squadra.
    squadre_per_canonico = {}

    for partita in partite:
        teams = partita.get("teams", {})

        for lato in ("home", "away"):
            nome = teams.get(lato, {}).get("name")
            if not nome:
                continue

            canonico = normalizza_nome_squadra(nome)
            display = PREFERRED_TEAM_DISPLAY_NAMES.get(canonico, nome)

            if canonico not in squadre_per_canonico:
                squadre_per_canonico[canonico] = display
            elif canonico in PREFERRED_TEAM_DISPLAY_NAMES:
                squadre_per_canonico[canonico] = display

    return sorted(
        squadre_per_canonico.values(),
        key=str.casefold,
    )


def get_team_last_matches(
    team_name,
    competizione=DEFAULT_COMPETITION,
    limit=5,
):
    dati = get_league_fixtures(competizione)["data"]
    partite = []

    for partita in dati:
        if partita.get("status") != "finished":
            continue

        casa = partita["teams"]["home"]["name"]
        ospite = partita["teams"]["away"]["name"]

        if (
            stessa_squadra(team_name, casa)
            or stessa_squadra(team_name, ospite)
        ):
            partite.append(partita)

    partite.sort(
        key=lambda p: p["kickoff_ts"],
        reverse=True,
    )

    return partite[:limit]


def trasforma_partite_squadra(partite, team_name):
    risultati = []

    for partita in partite:
        casa = partita["teams"]["home"]["name"]
        ospite = partita["teams"]["away"]["name"]

        squadra_casa = stessa_squadra(team_name, casa)
        squadra_ospite = stessa_squadra(team_name, ospite)

        if not squadra_casa and not squadra_ospite:
            continue

        if squadra_casa:
            lato = "home"
            lato_avversario = "away"
            avversario = ospite
            casa_trasferta = "casa"
        else:
            lato = "away"
            lato_avversario = "home"
            avversario = casa
            casa_trasferta = "trasferta"

        gol_fatti = partita["goals"][lato]
        gol_subiti = partita["goals"][lato_avversario]
        corner = partita["corners"][lato]
        ammonizioni = partita["cards"][lato]["yellow"]

        try:
            statistiche = get_fixture_stats(partita["id"])
        except requests.RequestException:
            # Le statistiche estese sono descrittive e non devono impedire
            # l'analisi xG principale. Manteniamo esplicitamente il dato come
            # mancante invece di trasformare un 429 in falsi zeri.
            statistiche = None

        def valore_statistica(nome):
            if not isinstance(statistiche, dict):
                return None
            return statistiche.get(nome, {}).get(lato)

        possesso = valore_statistica("possession")
        tiri_in_porta = valore_statistica("shots_on_target")
        tiri_fuori = valore_statistica("shots_off_target")
        attacchi = valore_statistica("attacks")
        attacchi_pericolosi = valore_statistica("dangerous_attacks")

        risultati.append({
            "data": partita["kickoff_utc"],
            "avversario": avversario,
            "competizione": partita["league"]["name"],
            "risultato": (
                f"{partita['goals']['home']}-"
                f"{partita['goals']['away']}"
            ),
            "gol_fatti": gol_fatti,
            "gol_subiti": gol_subiti,
            "corner": corner,
            "ammonizioni": ammonizioni,
            "possesso": possesso,
            "tiri_in_porta": tiri_in_porta,
            "tiri_fuori": tiri_fuori,
            "attacchi": attacchi,
            "attacchi_pericolosi": attacchi_pericolosi,
            "statistiche_provider_disponibili": isinstance(statistiche, dict),
            "casa_trasferta": casa_trasferta,
        })

    return risultati


def calcola_media_gol_campionato(competizione=DEFAULT_COMPETITION):
    partite = get_league_fixtures(competizione)["data"]

    partite_finite = [
        p for p in partite
        if p.get("status") == "finished"
    ]

    if not partite_finite:
        return 0

    gol_totali = sum(
        p["goals"]["home"] + p["goals"]["away"]
        for p in partite_finite
    )

    return round(
        gol_totali / (len(partite_finite) * 2),
        2,
    )


def get_understat_league_data(
    competizione=DEFAULT_COMPETITION,
    season=None,
):
    config = get_competition_config(competizione)
    season = season or _current_understat_season()
    cache_key = f"{config['slug']}:{season}"
    now = time.monotonic()

    with _UNDERSTAT_CACHE_LOCK:
        cached = _UNDERSTAT_CACHE.get(cache_key)

        if cached is not None and now < cached["expires_at"]:
            return cached["value"]

        url = (
            "https://understat.com/getLeagueData/"
            f"{config['understat_league']}/{season}"
        )

        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://understat.com/",
            },
            timeout=15,
        )

        response.raise_for_status()
        dati = response.json()

        _UNDERSTAT_CACHE[cache_key] = {
            "expires_at": (
                time.monotonic()
                + UNDERSTAT_CACHE_TTL_SECONDS
            ),
            "value": dati,
        }

        return dati


def get_understat_team_matches(
    team_name,
    competizione=DEFAULT_COMPETITION,
    limit=5,
):
    dati = get_understat_league_data(competizione)
    partite = []

    for partita in dati["dates"]:
        if not partita["isResult"]:
            continue

        casa = partita["h"]["title"]
        ospite = partita["a"]["title"]

        squadra_casa = stessa_squadra(team_name, casa)
        squadra_ospite = stessa_squadra(team_name, ospite)

        if not squadra_casa and not squadra_ospite:
            continue

        if squadra_casa:
            xg_fatti = float(partita["xG"]["h"])
            xg_subiti = float(partita["xG"]["a"])
            casa_trasferta = "casa"
            avversario = ospite
        else:
            xg_fatti = float(partita["xG"]["a"])
            xg_subiti = float(partita["xG"]["h"])
            casa_trasferta = "trasferta"
            avversario = casa

        partite.append({
            "data": partita["datetime"],
            "avversario": avversario,
            "xg_fatti": xg_fatti,
            "xg_subiti": xg_subiti,
            "casa_trasferta": casa_trasferta,
        })

    partite.sort(
        key=lambda p: p["data"],
        reverse=True,
    )

    return partite[:limit]


def get_fixture_stats(fixture_id):
    cache_key = str(fixture_id)
    now = time.time()

    with _FIXTURE_STATS_CACHE_LOCK:
        cached = _FIXTURE_STATS_CACHE.get(cache_key)

        if cached is None:
            cached = _load_provider_disk_cache(
                "fixture_stats",
                cache_key,
                FIXTURE_STATS_CACHE_TTL_SECONDS,
                FIXTURE_STATS_STALE_TTL_SECONDS,
            )
            if cached is not None:
                _FIXTURE_STATS_CACHE[cache_key] = cached

        if cached is not None and now < cached["expires_at"]:
            return cached["value"]

        stale_value = _stale_cache_value(cached, now)

        url = (
            f"{BASE_URL}/fixtures/"
            f"{fixture_id}"
        )

        headers = {
            "Authorization": f"Bearer {API_KEY}"
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                params={"include": "stats"},
                timeout=15,
            )
            response.raise_for_status()
            dati = response.json()
        except requests.RequestException:
            if stale_value is not None:
                return stale_value
            raise

        statistiche = (
            dati
            .get("data", {})
            .get("statistics", {})
        )

        entry = _build_cache_entry(
            statistiche,
            FIXTURE_STATS_CACHE_TTL_SECONDS,
            FIXTURE_STATS_STALE_TTL_SECONDS,
        )
        _FIXTURE_STATS_CACHE[cache_key] = entry
        _save_provider_disk_cache(
            "fixture_stats",
            cache_key,
            statistiche,
        )

        return statistiche
