import os
import time
from threading import Lock

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("FOOTBALL_API_KEY")
BASE_URL = "https://api.5dollarfootballapi.com/v1"
SERIE_A_ID = 3405541143

# Cache tecnica per ridurre chiamate duplicate al provider.
#
# Fixture di campionato:
# 60 secondi, così risultati/calendario restano molto freschi.
#
# Statistiche fixture:
# 1 ora. Attualmente vengono richieste soltanto per partite
# già terminate tramite get_team_last_matches().
FIXTURES_CACHE_TTL_SECONDS = 60
FIXTURE_STATS_CACHE_TTL_SECONDS = 3600

_FIXTURES_CACHE = {
    "expires_at": 0.0,
    "value": None,
}

_FIXTURE_STATS_CACHE = {}

_FIXTURES_CACHE_LOCK = Lock()
_FIXTURE_STATS_CACHE_LOCK = Lock()


# ============================================================
# MATCHING ROBUSTO NOMI SQUADRE
#
# Vietato usare confronti a sottostringa come:
#     "milan" in "inter milan"
#
# perché produce falsi positivi.
# ============================================================

TEAM_ALIASES = {
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
}


def normalizza_nome_squadra(nome):
    nome = str(nome).strip().lower()

    # Normalizzazione minima della punteggiatura.
    for carattere in [".", "-", "_"]:
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


def get_serie_a_fixtures():
    now = time.monotonic()

    with _FIXTURES_CACHE_LOCK:
        cached = _FIXTURES_CACHE["value"]

        if (
            cached is not None
            and now < _FIXTURES_CACHE["expires_at"]
        ):
            return cached

        url = (
            f"{BASE_URL}/leagues/"
            f"{SERIE_A_ID}/fixtures"
        )

        headers = {
            "Authorization": f"Bearer {API_KEY}"
        }

        tutte_le_partite = []

        for pagina in range(1, 4):
            params = {
                "page": pagina,
                "per_page": 100
            }

            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=15
            )

            response.raise_for_status()

            dati = response.json()
            partite = dati.get("data", [])

            tutte_le_partite.extend(
                partite
            )

            if len(partite) < 100:
                break

        risultato = {
            "data": tutte_le_partite
        }

        _FIXTURES_CACHE["value"] = risultato
        _FIXTURES_CACHE["expires_at"] = (
            time.monotonic()
            + FIXTURES_CACHE_TTL_SECONDS
        )

        return risultato

def get_team_last_matches(team_name, limit=5):
    dati = get_serie_a_fixtures()["data"]

    partite = []

    for partita in dati:
        if partita["status"] != "finished":
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
        reverse=True
    )

    return partite[:limit]
def trasforma_partite_squadra(partite, team_name):
    risultati = []

    for partita in partite:
        casa = partita["teams"]["home"]["name"]
        ospite = partita["teams"]["away"]["name"]

        squadra_casa = stessa_squadra(
            team_name,
            casa
        )

        squadra_ospite = stessa_squadra(
            team_name,
            ospite
        )

        if not squadra_casa and not squadra_ospite:
            # Sicurezza: una partita estranea non deve
            # mai essere attribuita alla squadra richiesta.
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

        statistiche = get_fixture_stats(
            partita["id"]
        )

        possesso = (
            statistiche
            .get("possession", {})
            .get(lato, 0)
        )

        tiri_in_porta = (
            statistiche
            .get("shots_on_target", {})
            .get(lato, 0)
        )

        tiri_fuori = (
            statistiche
            .get("shots_off_target", {})
            .get(lato, 0)
        )

        attacchi = (
            statistiche
            .get("attacks", {})
            .get(lato, 0)
        )

        attacchi_pericolosi = (
            statistiche
            .get("dangerous_attacks", {})
            .get(lato, 0)
        )

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
            "attacchi_pericolosi":
                attacchi_pericolosi,
            "casa_trasferta":
                casa_trasferta,
        })

    return risultati

def calcola_media_gol_campionato():
    partite = get_serie_a_fixtures()["data"]

    partite_finite = [
        p for p in partite
        if p["status"] == "finished"
    ]

    if not partite_finite:
        return 0

    gol_totali = sum(
        p["goals"]["home"] + p["goals"]["away"]
        for p in partite_finite
    )

    return round(
        gol_totali / (len(partite_finite) * 2),
        2
    )


def get_understat_team_matches(team_name, limit=5):
    url = "https://understat.com/getLeagueData/Serie_A/2026"

    response = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://understat.com/"
        },
        timeout=15
    )

    response.raise_for_status()

    dati = response.json()

    partite = []

    for partita in dati["dates"]:
        if not partita["isResult"]:
            continue

        casa = partita["h"]["title"]
        ospite = partita["a"]["title"]

        squadra_casa = stessa_squadra(
            team_name,
            casa
        )

        squadra_ospite = stessa_squadra(
            team_name,
            ospite
        )

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
            "casa_trasferta": casa_trasferta
        })

    partite.sort(
        key=lambda p: p["data"],
        reverse=True
    )

    return partite[:limit]


def get_fixture_stats(fixture_id):
    cache_key = str(fixture_id)
    now = time.monotonic()

    with _FIXTURE_STATS_CACHE_LOCK:
        cached = _FIXTURE_STATS_CACHE.get(
            cache_key
        )

        if (
            cached is not None
            and now < cached["expires_at"]
        ):
            return cached["value"]

        url = (
            f"{BASE_URL}/fixtures/"
            f"{fixture_id}"
        )

        headers = {
            "Authorization": f"Bearer {API_KEY}"
        }

        response = requests.get(
            url,
            headers=headers,
            params={"include": "stats"},
            timeout=15
        )

        response.raise_for_status()

        dati = response.json()

        statistiche = (
            dati
            .get("data", {})
            .get("statistics", {})
        )

        _FIXTURE_STATS_CACHE[
            cache_key
        ] = {
            "expires_at": (
                time.monotonic()
                + FIXTURE_STATS_CACHE_TTL_SECONDS
            ),
            "value": statistiche,
        }

        return statistiche
