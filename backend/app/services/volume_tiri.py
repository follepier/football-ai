"""
Correttore Volume Tiri - Ridge Regression.

Il modello usa esclusivamente informazioni disponibili prima
della partita da analizzare.

La correzione viene appresa dai residui della baseline ufficiale:

    residuo casa   = gol reali casa   - gol attesi baseline casa
    residuo ospite = gol reali ospite - gol attesi baseline ospite

Il volume tiri è:

    (tiri in porta casa + tiri fuori casa)
    -
    (tiri in porta ospite + tiri fuori ospite)
"""

import csv
import math
from pathlib import Path

from sklearn.linear_model import Ridge


ALPHA = 200.0

FEATURES_PATH = Path("data/serie_a_features.csv")
BASELINE_PATH = Path("data/serie_a_backtest_baseline.csv")


def calcola_volume_tiri(
    casa_tiri_in_porta,
    casa_tiri_fuori,
    ospite_tiri_in_porta,
    ospite_tiri_fuori,
):
    volume_casa = (
        float(casa_tiri_in_porta)
        + float(casa_tiri_fuori)
    )

    volume_ospite = (
        float(ospite_tiri_in_porta)
        + float(ospite_tiri_fuori)
    )

    return volume_casa - volume_ospite


def _numero(valore):
    if valore in ("", None):
        return 0.0

    return float(valore)


def costruisci_storico_volume(
    data_partita,
    features_path=FEATURES_PATH,
    baseline_path=BASELINE_PATH,
):
    """
    Costruisce lo storico walk-forward.

    Sono utilizzate esclusivamente partite precedenti
    alla data della partita corrente.

    Restituisce:
        storico_volume
        storico_residui_casa
        storico_residui_ospite
    """

    with open(features_path, encoding="utf-8") as f:
        features = list(csv.DictReader(f))

    with open(baseline_path, encoding="utf-8") as f:
        baseline = list(csv.DictReader(f))

    indice_features = {
        (r["data"], r["casa"], r["ospite"]): r
        for r in features
    }

    storico_volume = []
    storico_residui_casa = []
    storico_residui_ospite = []

    for riga in baseline:
        if riga["data"] >= data_partita:
            continue

        chiave = (
            riga["data"],
            riga["casa"],
            riga["ospite"],
        )

        feature = indice_features.get(chiave)

        if feature is None:
            continue

        volume = calcola_volume_tiri(
            _numero(
                feature["casa_tiri_in_porta_totale_pre"]
            ),
            _numero(
                feature["casa_tiri_fuori_totale_pre"]
            ),
            _numero(
                feature["ospite_tiri_in_porta_totale_pre"]
            ),
            _numero(
                feature["ospite_tiri_fuori_totale_pre"]
            ),
        )

        gol_casa = float(riga["gol_casa_reali"])
        gol_ospite = float(riga["gol_ospite_reali"])

        base_casa = float(riga["gol_casa_attesi"])
        base_ospite = float(riga["gol_ospite_attesi"])

        residuo_casa = gol_casa - base_casa
        residuo_ospite = gol_ospite - base_ospite

        storico_volume.append(volume)
        storico_residui_casa.append(residuo_casa)
        storico_residui_ospite.append(residuo_ospite)

    return (
        storico_volume,
        storico_residui_casa,
        storico_residui_ospite,
    )


def stima_correttiva_volume_tiri(
    volume_attuale,
    storico_volume,
    storico_residui_casa,
    storico_residui_ospite,
    alpha=ALPHA,
):
    """
    Allena due Ridge Regression separate:

        volume -> residuo casa
        volume -> residuo ospite

    e restituisce le due correzioni.
    """

    if not storico_volume:
        return 0.0, 0.0

    X = [
        [float(volume)]
        for volume in storico_volume
    ]

    modello_casa = Ridge(alpha=alpha)
    modello_ospite = Ridge(alpha=alpha)

    modello_casa.fit(
        X,
        [float(x) for x in storico_residui_casa],
    )

    modello_ospite.fit(
        X,
        [float(x) for x in storico_residui_ospite],
    )

    correzione_casa = modello_casa.predict(
        [[float(volume_attuale)]]
    )[0]

    correzione_ospite = modello_ospite.predict(
        [[float(volume_attuale)]]
    )[0]

    return (
        float(correzione_casa),
        float(correzione_ospite),
    )


def applica_correzione_volume_tiri(
    gol_attesi_casa_baseline,
    gol_attesi_ospite_baseline,
    correzione_casa,
    correzione_ospite,
):
    """
    Applica la correzione alla baseline.

    I gol attesi non possono diventare negativi.
    """

    gol_casa = max(
        0.0,
        float(gol_attesi_casa_baseline)
        + float(correzione_casa),
    )

    gol_ospite = max(
        0.0,
        float(gol_attesi_ospite_baseline)
        + float(correzione_ospite),
    )

    return gol_casa, gol_ospite


def correggi_previsione(
    data_partita,
    volume_attuale,
    gol_attesi_casa_baseline,
    gol_attesi_ospite_baseline,
):
    """
    Funzione completa per ottenere i gol attesi corretti.

    Se non esiste storico sufficiente, restituisce
    esclusivamente la baseline.
    """

    (
        storico_volume,
        storico_residui_casa,
        storico_residui_ospite,
    ) = costruisci_storico_volume(
        data_partita
    )

    # Coerente con il backtest ufficiale:
    # le prime 3 partite usano esclusivamente la baseline.
    if len(storico_volume) < 3:
        return (
            float(gol_attesi_casa_baseline),
            float(gol_attesi_ospite_baseline),
            0.0,
            0.0,
        )

    (
        correzione_casa,
        correzione_ospite,
    ) = stima_correttiva_volume_tiri(
        volume_attuale,
        storico_volume,
        storico_residui_casa,
        storico_residui_ospite,
        alpha=ALPHA,
    )

    (
        gol_casa,
        gol_ospite,
    ) = applica_correzione_volume_tiri(
        gol_attesi_casa_baseline,
        gol_attesi_ospite_baseline,
        correzione_casa,
        correzione_ospite,
    )

    return (
        gol_casa,
        gol_ospite,
        correzione_casa,
        correzione_ospite,
    )
