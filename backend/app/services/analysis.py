import math
import statistics
from collections import defaultdict

from app.services.competitions import (
    DEFAULT_COMPETITION,
    get_competition_config,
)
from app.services.football_api import (
    get_understat_league_data,
    normalizza_nome_squadra,
)
from app.services.team_data import shrinkage_media


# ============================================================
# CALIBRAZIONI ENGINE XG
#
# La calibrazione Serie A e' quella gia validata out-of-sample
# nella v0.6.0. Gli altri campionati entrano inizialmente con
# trasformazione identita' (lambda finale = lambda raw) finche'
# non completiamo un backtest dedicato per ciascuna competizione.
# ============================================================

CALIBRAZIONI_XG = {
    "serie-a": {
        "intercetta": 0.214047,
        "pendenza": 0.765037,
        "validata": True,
    },
}

CALIBRAZIONE_XG_INTERCETTA = 0.214047
CALIBRAZIONE_XG_PENDENZA = 0.765037


def get_calibrazione_xg(competizione=DEFAULT_COMPETITION):
    config = get_competition_config(competizione)

    return CALIBRAZIONI_XG.get(
        config["slug"],
        {
            "intercetta": 0.0,
            "pendenza": 1.0,
            "validata": False,
        },
    )


def calibra_gol_attesi_xg(
    valore,
    competizione=DEFAULT_COMPETITION,
):
    calibrazione = get_calibrazione_xg(competizione)

    return max(
        0.0,
        calibrazione["intercetta"]
        + calibrazione["pendenza"] * float(valore),
    )


def probabilita_poisson(lam, gol):
    if lam <= 0:
        return 1.0 if gol == 0 else 0.0

    return (math.exp(-lam) * (lam ** gol)) / math.factorial(gol)


def costruisci_dati_xg(competizione=DEFAULT_COMPETITION):
    dati = get_understat_league_data(competizione)

    contesto = {
        "casa": defaultdict(list),
        "trasferta": defaultdict(list),
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
            "subiti": xg_ospite,
        })

        contesto["trasferta"][ospite].append({
            "fatti": xg_ospite,
            "subiti": xg_casa,
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
            "varianza_osservazioni": 0.0,
        }

    media = statistics.mean(medie)
    varianza_tra = statistics.pvariance(medie)

    if varianze:
        varianza_osservazioni = statistics.mean(varianze)
    else:
        varianza_osservazioni = 0.0

    correzione = statistics.mean(
        varianza_osservazioni / len(squadre[nome])
        for nome in squadre
        if len(squadre[nome]) > 0
    )

    varianza_tra = max(
        varianza_tra - correzione,
        0.0,
    )

    return {
        "media": media,
        "varianza_tra": varianza_tra,
        "varianza_osservazioni": varianza_osservazioni,
    }


def trova_squadra(contesto, nome):
    nome_norm = normalizza_nome_squadra(nome)

    # Prima corrispondenza normalizzata esatta.
    for squadra in contesto:
        if normalizza_nome_squadra(squadra) == nome_norm:
            return squadra

    # Fallback bidirezionale per differenze innocue tra provider
    # e Understat (es. suffissi FC). L'input del frontend viene
    # comunque proposto dalla lista squadre del provider.
    for squadra in contesto:
        squadra_norm = normalizza_nome_squadra(squadra)

        if (
            nome_norm in squadra_norm
            or squadra_norm in nome_norm
        ):
            return squadra

    return None


def stima_forze(squadra, tipo, contesto):
    nome_reale = trova_squadra(contesto[tipo], squadra)

    if nome_reale is None:
        statistiche_attacco = statistiche_contesto(
            contesto[tipo],
            "fatti",
        )

        statistiche_difesa = statistiche_contesto(
            contesto[tipo],
            "subiti",
        )

        return {
            "attacco": 1.0,
            "difesa": 1.0,
            "partite": 0,
            "xg_fatti": statistiche_attacco["media"],
            "xg_subiti": statistiche_difesa["media"],
            "media_contesto_attacco": statistiche_attacco["media"],
            "media_contesto_difesa": statistiche_difesa["media"],
        }

    partite = contesto[tipo][nome_reale]

    statistiche_attacco = statistiche_contesto(
        contesto[tipo],
        "fatti",
    )

    statistiche_difesa = statistiche_contesto(
        contesto[tipo],
        "subiti",
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
        statistiche_attacco["varianza_osservazioni"],
    )

    difesa_shrink = shrinkage_media(
        media_difesa,
        numero_partite,
        statistiche_difesa["media"],
        statistiche_difesa["varianza_tra"],
        statistiche_difesa["varianza_osservazioni"],
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
        "media_contesto_difesa": statistiche_difesa["media"],
    }


def calcola_analisi(
    dati_casa,
    dati_ospite,
    competizione=DEFAULT_COMPETITION,
):
    config = get_competition_config(competizione)
    calibrazione = get_calibrazione_xg(config["slug"])

    contesto = costruisci_dati_xg(config["slug"])

    forza_casa = stima_forze(
        dati_casa["nome"],
        "casa",
        contesto,
    )

    forza_ospite = stima_forze(
        dati_ospite["nome"],
        "trasferta",
        contesto,
    )

    media_xg_casa = statistiche_contesto(
        contesto["casa"],
        "fatti",
    )["media"]

    media_xg_trasferta = statistiche_contesto(
        contesto["trasferta"],
        "fatti",
    )["media"]

    gol_attesi_casa_raw = (
        media_xg_casa
        * forza_casa["attacco"]
        * forza_ospite["difesa"]
    )

    gol_attesi_ospite_raw = (
        media_xg_trasferta
        * forza_ospite["attacco"]
        * forza_casa["difesa"]
    )

    gol_attesi_casa = calibra_gol_attesi_xg(
        gol_attesi_casa_raw,
        config["slug"],
    )

    gol_attesi_ospite = calibra_gol_attesi_xg(
        gol_attesi_ospite_raw,
        config["slug"],
    )

    gol_attesi_totali = (
        gol_attesi_casa + gol_attesi_ospite
    )

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
                    gol_c,
                )
                * probabilita_poisson(
                    gol_attesi_ospite,
                    gol_o,
                )
            )

            risultati.append({
                "risultato": f"{gol_c}-{gol_o}",
                "probabilita": probabilita,
            })

    risultati.sort(
        key=lambda x: x["probabilita"],
        reverse=True,
    )

    risultati_esatti = [
        {
            "risultato": r["risultato"],
            "probabilita": round(
                r["probabilita"] * 100,
                2,
            ),
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
                    r["risultato"].split("-"),
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
        "competizione": config["name"],
        "competizione_slug": config["slug"],
        "gol_attesi_casa": round(gol_attesi_casa, 2),
        "gol_attesi_ospite": round(gol_attesi_ospite, 2),
        "gol_attesi_totali": round(gol_attesi_totali, 2),
        "gol_attesi_casa_raw": round(
            gol_attesi_casa_raw,
            4,
        ),
        "gol_attesi_ospite_raw": round(
            gol_attesi_ospite_raw,
            4,
        ),
        "calibrazione_xg": {
            "intercetta": calibrazione["intercetta"],
            "pendenza": calibrazione["pendenza"],
            "validata": calibrazione["validata"],
        },
        "volume_tiri": {
            "casa": round(volume_tiri_casa, 2),
            "ospite": round(volume_tiri_ospite, 2),
            "differenziale": round(
                differenziale_volume_tiri,
                2,
            ),
        },
        "xg_casa_shrinkage": forza_casa["xg_fatti"],
        "xg_casa_subiti_shrinkage": forza_casa["xg_subiti"],
        "xg_ospite_shrinkage": forza_ospite["xg_fatti"],
        "xg_ospite_subiti_shrinkage": forza_ospite["xg_subiti"],
        "forza_attacco_casa": round(
            forza_casa["attacco"], 4,
        ),
        "forza_difesa_casa": round(
            forza_casa["difesa"], 4,
        ),
        "forza_attacco_ospite": round(
            forza_ospite["attacco"], 4,
        ),
        "forza_difesa_ospite": round(
            forza_ospite["difesa"], 4,
        ),
        "partite_casa_utilizzate": forza_casa["partite"],
        "partite_ospite_utilizzate": forza_ospite["partite"],
        "corner_casa": dati_casa.get(
            "corner_medi", 0,
        ),
        "corner_ospite": dati_ospite.get(
            "corner_medi", 0,
        ),
        "ammonizioni_casa": dati_casa.get(
            "ammonizioni_medie", 0,
        ),
        "ammonizioni_ospite": dati_ospite.get(
            "ammonizioni_medie", 0,
        ),
        "1x2": {
            "1": round(probabilita_1 * 100, 2),
            "X": round(probabilita_x * 100, 2),
            "2": round(probabilita_2 * 100, 2),
        },
        "doppia_chance": {
            "1X": round(
                (probabilita_1 + probabilita_x) * 100,
                2,
            ),
            "X2": round(
                (probabilita_x + probabilita_2) * 100,
                2,
            ),
            "12": round(
                (probabilita_1 + probabilita_2) * 100,
                2,
            ),
        },
        "over_under": {
            "over_1_5": round(over_15 * 100, 2),
            "under_1_5": round(
                (1 - over_15) * 100,
                2,
            ),
            "over_2_5": round(over_25 * 100, 2),
            "under_2_5": round(
                (1 - over_25) * 100,
                2,
            ),
            "over_3_5": round(over_35 * 100, 2),
            "under_3_5": round(
                (1 - over_35) * 100,
                2,
            ),
        },
        "gol_no_gol": {
            "gol": round(
                probabilita_gol * 100,
                2,
            ),
            "no_gol": round(
                (1 - probabilita_gol) * 100,
                2,
            ),
        },
        "risultati_esatti": risultati_esatti,
    }
