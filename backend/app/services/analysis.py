import math
import statistics
from collections import defaultdict

from app.services.football_api import (
    calcola_media_gol_campionato,
    get_understat_team_matches
)
from app.services.team_data import shrinkage_media


def probabilita_poisson(lam, gol):
    if lam <= 0:
        return 1.0 if gol == 0 else 0.0

    return (math.exp(-lam) * (lam ** gol)) / math.factorial(gol)


def costruisci_dati_xg():
    partite = []

    url_data = get_understat_team_matches

    # Recuperiamo un campione ampio del campionato attraverso
    # il singolo endpoint Understat già utilizzato dal progetto.
    import requests

    response = requests.get(
        "https://understat.com/getLeagueData/Serie_A/2026",
        headers={
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://understat.com/"
        },
        timeout=15
    )

    response.raise_for_status()
    dati = response.json()

    contesto = {
        "casa": defaultdict(list),
        "trasferta": defaultdict(list)
    }

    for partita in dati["dates"]:
        if not partita["isResult"]:
            continue

        casa = partita["h"]["title"]
        ospite = partita["a"]["title"]

        xg_casa = float(partita["xG"]["h"])
        xg_ospite = float(partita["xG"]["a"])

        contesto["casa"][casa].append({
            "fatti": xg_casa,
            "subiti": xg_ospite
        })

        contesto["trasferta"][ospite].append({
            "fatti": xg_ospite,
            "subiti": xg_casa
        })

    return contesto


def statistiche_contesto(squadre, campo):
    medie = []
    varianze = []

    for partite in squadre.values():
        valori = [p[campo] for p in partite]

        if not valori:
            continue

        medie.append(statistics.mean(valori))

        if len(valori) > 1:
            varianze.append(statistics.pvariance(valori))

    if not medie:
        return {
            "media": 0.0,
            "varianza_tra": 0.0,
            "varianza_osservazioni": 0.0
        }

    media = statistics.mean(medie)
    varianza_tra = statistics.pvariance(medie)

    if varianze:
        varianza_osservazioni = statistics.mean(varianze)
    else:
        varianza_osservazioni = 0.0

    # Correggiamo la varianza tra squadre per la variabilità
    # dovuta al campionamento quando possibile.
    correzione = statistics.mean(
        varianza_osservazioni / len(squadre[nome])
        for nome in squadre
        if len(squadre[nome]) > 0
    )

    varianza_tra = max(
        varianza_tra - correzione,
        0.0
    )

    return {
        "media": media,
        "varianza_tra": varianza_tra,
        "varianza_osservazioni": varianza_osservazioni
    }


def trova_squadra(contesto, nome):
    nome = nome.lower()

    for squadra in contesto:
        if squadra.lower() == nome:
            return squadra

    for squadra in contesto:
        if nome in squadra.lower():
            return squadra

    return None


def stima_forze(squadra, tipo, contesto):
    nome_reale = trova_squadra(contesto[tipo], squadra)

    if nome_reale is None:
        return {
            "attacco": 1.0,
            "difesa": 1.0,
            "partite": 0
        }

    partite = contesto[tipo][nome_reale]

    statistiche_attacco = statistiche_contesto(
        contesto[tipo],
        "fatti"
    )

    statistiche_difesa = statistiche_contesto(
        contesto[tipo],
        "subiti"
    )

    numero_partite = len(partite)

    media_attacco = statistics.mean(
        p["fatti"] for p in partite
    )

    media_difesa = statistics.mean(
        p["subiti"] for p in partite
    )

    attacco_shrink = shrinkage_media(
        media_attacco,
        numero_partite,
        statistiche_attacco["media"],
        statistiche_attacco["varianza_tra"],
        statistiche_attacco["varianza_osservazioni"]
    )

    difesa_shrink = shrinkage_media(
        media_difesa,
        numero_partite,
        statistiche_difesa["media"],
        statistiche_difesa["varianza_tra"],
        statistiche_difesa["varianza_osservazioni"]
    )

    if statistiche_attacco["media"] > 0:
        forza_attacco = (
            attacco_shrink / statistiche_attacco["media"]
        )
    else:
        forza_attacco = 1.0

    if statistiche_difesa["media"] > 0:
        forza_difesa = (
            difesa_shrink / statistiche_difesa["media"]
        )
    else:
        forza_difesa = 1.0

    return {
        "attacco": forza_attacco,
        "difesa": forza_difesa,
        "partite": numero_partite,
        "xg_fatti": attacco_shrink,
        "xg_subiti": difesa_shrink,
        "media_contesto_attacco": statistiche_attacco["media"],
        "media_contesto_difesa": statistiche_difesa["media"]
    }


def calcola_analisi(dati_casa, dati_ospite):
    gol_casa = dati_casa.get("gol_fatti", 0)
    gol_subiti_casa = dati_casa.get("gol_subiti", 0)

    gol_ospite = dati_ospite.get("gol_fatti", 0)
    gol_subiti_ospite = dati_ospite.get("gol_subiti", 0)

    media_gol_campionato = calcola_media_gol_campionato()

    contesto = costruisci_dati_xg()

    forza_casa = stima_forze(
        dati_casa["nome"],
        "casa",
        contesto
    )

    forza_ospite = stima_forze(
        dati_ospite["nome"],
        "trasferta",
        contesto
    )

    media_xg_casa = statistiche_contesto(
        contesto["casa"],
        "fatti"
    )["media"]

    media_xg_trasferta = statistiche_contesto(
        contesto["trasferta"],
        "fatti"
    )["media"]

    gol_attesi_casa = (
        media_xg_casa
        * forza_casa["attacco"]
        * forza_ospite["difesa"]
    )

    gol_attesi_ospite = (
        media_xg_trasferta
        * forza_ospite["attacco"]
        * forza_casa["difesa"]
    )

    gol_attesi_totali = (
        gol_attesi_casa + gol_attesi_ospite
    )

    # Volume tiri pre-partita.
    # Il differenziale è:
    # volume casa - volume ospite
    volume_tiri_casa = (
        dati_casa.get("tiri_in_porta_medi", 0)
        + dati_casa.get("tiri_fuori_medi", 0)
    )

    volume_tiri_ospite = (
        dati_ospite.get("tiri_in_porta_medi", 0)
        + dati_ospite.get("tiri_fuori_medi", 0)
    )

    differenziale_volume_tiri = (
        volume_tiri_casa - volume_tiri_ospite
    )

    risultati = []

    for gol_c in range(21):
        for gol_o in range(21):
            probabilita = (
                probabilita_poisson(
                    gol_attesi_casa,
                    gol_c
                )
                * probabilita_poisson(
                    gol_attesi_ospite,
                    gol_o
                )
            )

            risultati.append({
                "risultato": f"{gol_c}-{gol_o}",
                "probabilita": probabilita
            })

    risultati.sort(
        key=lambda x: x["probabilita"],
        reverse=True
    )

    risultati_esatti = [
        {
            "risultato": r["risultato"],
            "probabilita": round(
                r["probabilita"] * 100,
                2
            )
        }
        for r in risultati[:5]
    ]

    probabilita_1 = sum(
        r["probabilita"]
        for r in risultati
        if int(r["risultato"].split("-")[0])
        > int(r["risultato"].split("-")[1])
    )

    probabilita_x = sum(
        r["probabilita"]
        for r in risultati
        if int(r["risultato"].split("-")[0])
        == int(r["risultato"].split("-")[1])
    )

    probabilita_2 = sum(
        r["probabilita"]
        for r in risultati
        if int(r["risultato"].split("-")[0])
        < int(r["risultato"].split("-")[1])
    )

    def probabilita_over(soglia):
        return sum(
            r["probabilita"]
            for r in risultati
            if sum(
                map(
                    int,
                    r["risultato"].split("-")
                )
            ) > soglia
        )

    over_15 = probabilita_over(1)
    over_25 = probabilita_over(2)
    over_35 = probabilita_over(3)

    probabilita_gol = sum(
        r["probabilita"]
        for r in risultati
        if int(r["risultato"].split("-")[0]) > 0
        and int(r["risultato"].split("-")[1]) > 0
    )

    return {
        "casa": dati_casa["nome"],
        "ospite": dati_ospite["nome"],

        "gol_attesi_casa": round(gol_attesi_casa, 2),
        "gol_attesi_ospite": round(gol_attesi_ospite, 2),
        "gol_attesi_totali": round(gol_attesi_totali, 2),

        "volume_tiri": {
            "casa": round(volume_tiri_casa, 2),
            "ospite": round(volume_tiri_ospite, 2),
            "differenziale": round(
                differenziale_volume_tiri,
                2
            )
        },

        "xg_casa_shrinkage": forza_casa["xg_fatti"],
        "xg_casa_subiti_shrinkage": forza_casa["xg_subiti"],
        "xg_ospite_shrinkage": forza_ospite["xg_fatti"],
        "xg_ospite_subiti_shrinkage": forza_ospite["xg_subiti"],

        "forza_attacco_casa": round(
            forza_casa["attacco"], 4
        ),
        "forza_difesa_casa": round(
            forza_casa["difesa"], 4
        ),
        "forza_attacco_ospite": round(
            forza_ospite["attacco"], 4
        ),
        "forza_difesa_ospite": round(
            forza_ospite["difesa"], 4
        ),

        "partite_casa_utilizzate": forza_casa["partite"],
        "partite_ospite_utilizzate": forza_ospite["partite"],

        "corner_casa": dati_casa.get(
            "corner_medi", 0
        ),
        "corner_ospite": dati_ospite.get(
            "corner_medi", 0
        ),

        "ammonizioni_casa": dati_casa.get(
            "ammonizioni_medie", 0
        ),
        "ammonizioni_ospite": dati_ospite.get(
            "ammonizioni_medie", 0
        ),

        "1x2": {
            "1": round(probabilita_1 * 100, 2),
            "X": round(probabilita_x * 100, 2),
            "2": round(probabilita_2 * 100, 2)
        },

        "doppia_chance": {
            "1X": round(
                (probabilita_1 + probabilita_x) * 100,
                2
            ),
            "X2": round(
                (probabilita_x + probabilita_2) * 100,
                2
            ),
            "12": round(
                (probabilita_1 + probabilita_2) * 100,
                2
            )
        },

        "over_under": {
            "over_1_5": round(over_15 * 100, 2),
            "under_1_5": round(
                (1 - over_15) * 100,
                2
            ),
            "over_2_5": round(over_25 * 100, 2),
            "under_2_5": round(
                (1 - over_25) * 100,
                2
            ),
            "over_3_5": round(over_35 * 100, 2),
            "under_3_5": round(
                (1 - over_35) * 100,
                2
            )
        },

        "gol_no_gol": {
            "gol": round(
                probabilita_gol * 100,
                2
            ),
            "no_gol": round(
                (1 - probabilita_gol) * 100,
                2
            )
        },

        "risultati_esatti": risultati_esatti
    }
