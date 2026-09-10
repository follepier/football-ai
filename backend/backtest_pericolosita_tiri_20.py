import csv
import math
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

DATASET = "../data/serie_a_features.csv"
BASELINE = "../data/serie_a_backtest_baseline.csv"
OUTPUT = "../data/serie_a_backtest_pericolosita_tiri_20.csv"


def numero(x):
    if x is None or x == "":
        return 0.0
    return float(x)


def rapporto(a, b):
    if b <= 0:
        return 0.0
    return a / b


# --------------------------------------------------
# CARICAMENTO
# --------------------------------------------------

with open(DATASET, encoding="utf-8") as f:
    dataset = list(csv.DictReader(f))

with open(BASELINE, encoding="utf-8") as f:
    baseline = list(csv.DictReader(f))


# --------------------------------------------------
# INDICE DELLE FEATURE PRE-PARTITA
# --------------------------------------------------

indice = {}

for r in dataset:

    chiave = (
        r["data"],
        r["casa"],
        r["ospite"]
    )

    # CASA
    casa_xg = numero(
        r["casa_xg_fatti_totale_pre"]
    )

    casa_xg_subiti = numero(
        r["casa_xg_subiti_totale_pre"]
    )

    casa_tiri_porta = numero(
        r["casa_tiri_in_porta_totale_pre"]
    )

    casa_tiri_fuori = numero(
        r["casa_tiri_fuori_totale_pre"]
    )

    casa_tiri_totali = (
        casa_tiri_porta
        + casa_tiri_fuori
    )

    # OSPITE
    ospite_xg = numero(
        r["ospite_xg_fatti_totale_pre"]
    )

    ospite_xg_subiti = numero(
        r["ospite_xg_subiti_totale_pre"]
    )

    ospite_tiri_porta = numero(
        r["ospite_tiri_in_porta_totale_pre"]
    )

    ospite_tiri_fuori = numero(
        r["ospite_tiri_fuori_totale_pre"]
    )

    ospite_tiri_totali = (
        ospite_tiri_porta
        + ospite_tiri_fuori
    )

    indice[chiave] = {

        # DIFFERENZE DI XG
        "xg_diff":
            casa_xg - ospite_xg,

        "xg_subiti_diff":
            casa_xg_subiti - ospite_xg_subiti,

        # QUALITA' MEDIA DEL TIRO
        "xg_per_tiro_casa":
            rapporto(
                casa_xg,
                casa_tiri_totali
            ),

        "xg_per_tiro_ospite":
            rapporto(
                ospite_xg,
                ospite_tiri_totali
            ),

        "xg_per_tiro_diff":
            rapporto(
                casa_xg,
                casa_tiri_totali
            )
            -
            rapporto(
                ospite_xg,
                ospite_tiri_totali
            ),

        # PRECISIONE
        "precisione_casa":
            rapporto(
                casa_tiri_porta,
                casa_tiri_totali
            ),

        "precisione_ospite":
            rapporto(
                ospite_tiri_porta,
                ospite_tiri_totali
            ),

        "precisione_diff":
            rapporto(
                casa_tiri_porta,
                casa_tiri_totali
            )
            -
            rapporto(
                ospite_tiri_porta,
                ospite_tiri_totali
            ),

        # FINALIZZAZIONE INDIRETTA:
        # non usiamo i gol della partita futura.
        # Usiamo soltanto xG e volume di tiro.
        "volume_tiri_diff":
            casa_tiri_totali
            - ospite_tiri_totali,

        "tiri_porta_diff":
            casa_tiri_porta
            - ospite_tiri_porta,
    }


# --------------------------------------------------
# COSTRUZIONE DELLE 20 PARTITE
# --------------------------------------------------

partite = []

for b in baseline:

    chiave = (
        b["data"],
        b["casa"],
        b["ospite"]
    )

    f = indice.get(chiave)

    if f is None:
        raise RuntimeError(
            f"Feature non trovate: {chiave}"
        )

    partite.append({

        "data": b["data"],
        "casa": b["casa"],
        "ospite": b["ospite"],

        "gol_casa":
            float(b["gol_casa_reali"]),

        "gol_ospite":
            float(b["gol_ospite_reali"]),

        "baseline_casa":
            float(b["gol_casa_attesi"]),

        "baseline_ospite":
            float(b["gol_ospite_attesi"]),

        **f
    })


# --------------------------------------------------
# VARIABILI
#
# Usiamo le differenze casa-ospite dove ha senso,
# così il modello valuta il vantaggio relativo.
# --------------------------------------------------

X = []

for p in partite:

    X.append([
        p["xg_diff"],
        p["xg_subiti_diff"],
        p["xg_per_tiro_diff"],
        p["precisione_diff"],
        p["volume_tiri_diff"],
        p["tiri_porta_diff"],
    ])


# --------------------------------------------------
# TARGET
#
# Il modello cerca di correggere l'errore
# del baseline.
# --------------------------------------------------

y_casa = [
    p["gol_casa"] - p["baseline_casa"]
    for p in partite
]

y_ospite = [
    p["gol_ospite"] - p["baseline_ospite"]
    for p in partite
]


# --------------------------------------------------
# LEAVE-ONE-OUT
# --------------------------------------------------

predizioni = []

for i, attuale in enumerate(partite):

    X_train = X[:i] + X[i + 1:]

    yc_train = y_casa[:i] + y_casa[i + 1:]
    yo_train = y_ospite[:i] + y_ospite[i + 1:]

    modello_casa = LinearRegression()
    modello_ospite = LinearRegression()

    modello_casa.fit(
        X_train,
        yc_train
    )

    modello_ospite.fit(
        X_train,
        yo_train
    )

    correzione_casa = float(
        modello_casa.predict([X[i]])[0]
    )

    correzione_ospite = float(
        modello_ospite.predict([X[i]])[0]
    )

    previsione_casa = (
        attuale["baseline_casa"]
        + correzione_casa
    )

    previsione_ospite = (
        attuale["baseline_ospite"]
        + correzione_ospite
    )

    predizioni.append({

        "data": attuale["data"],
        "casa": attuale["casa"],
        "ospite": attuale["ospite"],

        "gol_casa_reali":
            attuale["gol_casa"],

        "gol_ospite_reali":
            attuale["gol_ospite"],

        "gol_casa_baseline":
            attuale["baseline_casa"],

        "gol_ospite_baseline":
            attuale["baseline_ospite"],

        "gol_casa_previsti":
            previsione_casa,

        "gol_ospite_previsti":
            previsione_ospite,
    })


# --------------------------------------------------
# METRICHE
# --------------------------------------------------

reali_casa = [
    p["gol_casa_reali"]
    for p in predizioni
]

previsti_casa = [
    p["gol_casa_previsti"]
    for p in predizioni
]

reali_ospite = [
    p["gol_ospite_reali"]
    for p in predizioni
]

previsti_ospite = [
    p["gol_ospite_previsti"]
    for p in predizioni
]


mae_casa = mean_absolute_error(
    reali_casa,
    previsti_casa
)

mae_ospite = mean_absolute_error(
    reali_ospite,
    previsti_ospite
)

rmse_casa = math.sqrt(
    mean_squared_error(
        reali_casa,
        previsti_casa
    )
)

rmse_ospite = math.sqrt(
    mean_squared_error(
        reali_ospite,
        previsti_ospite
    )
)

mae_medio = (
    mae_casa + mae_ospite
) / 2

rmse_medio = (
    rmse_casa + rmse_ospite
) / 2


# --------------------------------------------------
# SALVATAGGIO
# --------------------------------------------------

with open(
    OUTPUT,
    "w",
    newline="",
    encoding="utf-8"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=predizioni[0].keys()
    )

    writer.writeheader()
    writer.writerows(predizioni)


# --------------------------------------------------
# RISULTATI
# --------------------------------------------------

print()
print("===== BASELINE + PERICOLOSITA' DEI TIRI =====")
print(f"Partite utilizzate: {len(partite)}")

print(f"MAE gol casa: {mae_casa:.4f}")
print(f"MAE gol ospite: {mae_ospite:.4f}")
print(f"MAE medio: {mae_medio:.4f}")

print(f"RMSE gol casa: {rmse_casa:.4f}")
print(f"RMSE gol ospite: {rmse_ospite:.4f}")
print(f"RMSE medio: {rmse_medio:.4f}")

print()
print("===== CONFRONTO =====")
print("Baseline MAE medio:  0.7683")
print(f"Nuovo MAE medio:      {mae_medio:.4f}")
print(f"Differenza MAE:       {mae_medio - 0.7683:+.4f}")

print("Baseline RMSE medio: 0.9473")
print(f"Nuovo RMSE medio:     {rmse_medio:.4f}")
print(f"Differenza RMSE:      {rmse_medio - 0.9473:+.4f}")

print()
print(f"File salvato: {OUTPUT}")
