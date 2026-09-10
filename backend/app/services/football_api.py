import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("FOOTBALL_API_KEY")
BASE_URL = "https://api.5dollarfootballapi.com/v1"
SERIE_A_ID = 3405541143


def get_serie_a_fixtures():
    url = f"{BASE_URL}/leagues/{SERIE_A_ID}/fixtures"

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

        tutte_le_partite.extend(partite)

        if len(partite) < 100:
            break

    return {"data": tutte_le_partite}

def get_team_last_matches(team_name, limit=5):
    dati = get_serie_a_fixtures()["data"]

    team_name = team_name.lower()

    partite = []

    for partita in dati:
        if partita["status"] != "finished":
            continue

        casa = partita["teams"]["home"]["name"].lower()
        ospite = partita["teams"]["away"]["name"].lower()

        if team_name in casa or team_name in ospite:
            partite.append(partita)

    partite.sort(
        key=lambda p: p["kickoff_ts"],
        reverse=True
    )

    return partite[:limit]
def trasforma_partite_squadra(partite, team_name):
    team_name = team_name.lower()

    risultati = []

    for partita in partite:
        casa = partita["teams"]["home"]["name"]
        ospite = partita["teams"]["away"]["name"]

        if team_name in casa.lower():
            gol_fatti = partita["goals"]["home"]
            gol_subiti = partita["goals"]["away"]
            corner = partita["corners"]["home"]
            ammonizioni = partita["cards"]["home"]["yellow"]

        else:
            gol_fatti = partita["goals"]["away"]
            gol_subiti = partita["goals"]["home"]
            corner = partita["corners"]["away"]
            ammonizioni = partita["cards"]["away"]["yellow"]

        statistiche = get_fixture_stats(partita["id"])

        if team_name in casa.lower():
            possesso = statistiche.get("possession", {}).get("home", 0)
            tiri_in_porta = statistiche.get("shots_on_target", {}).get("home", 0)
            tiri_fuori = statistiche.get("shots_off_target", {}).get("home", 0)
            attacchi = statistiche.get("attacks", {}).get("home", 0)
            attacchi_pericolosi = statistiche.get("dangerous_attacks", {}).get("home", 0)
        else:
            possesso = statistiche.get("possession", {}).get("away", 0)
            tiri_in_porta = statistiche.get("shots_on_target", {}).get("away", 0)
            tiri_fuori = statistiche.get("shots_off_target", {}).get("away", 0)
            attacchi = statistiche.get("attacks", {}).get("away", 0)
            attacchi_pericolosi = statistiche.get("dangerous_attacks", {}).get("away", 0)

        risultati.append({
            "data": partita["kickoff_utc"],
            "avversario": ospite if team_name in casa.lower() else casa,
            "competizione": partita["league"]["name"],
            "risultato": f"{partita['goals']['home']}-{partita['goals']['away']}",
            "gol_fatti": gol_fatti,
            "gol_subiti": gol_subiti,
            "corner": corner,
            "ammonizioni": ammonizioni,
            "possesso": possesso,
            "tiri_in_porta": tiri_in_porta,
            "tiri_fuori": tiri_fuori,
            "attacchi": attacchi,
            "attacchi_pericolosi": attacchi_pericolosi,
            "casa_trasferta": "casa" if team_name in casa.lower() else "trasferta",
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
    team_name = team_name.lower()

    partite = []

    for partita in dati["dates"]:
        if not partita["isResult"]:
            continue

        casa = partita["h"]["title"]
        ospite = partita["a"]["title"]

        if team_name not in casa.lower() and team_name not in ospite.lower():
            continue

        if team_name in casa.lower():
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
    url = f"{BASE_URL}/fixtures/{fixture_id}"

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

    return dati.get("data", {}).get("statistics", {})
