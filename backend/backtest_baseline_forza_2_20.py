import csv
import math
from collections import defaultdict
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

DATASET = "../data/serie_a_dataset.csv"
BASELINE = "../data/serie_a_backtest_baseline.csv"
OUTPUT = "../data/serie_a_backtest_baseline_forza_2_20.csv"


# --------------------------------------------------
# CARICAMENTO
# --------------------------------------------------

with open(DATASET, encoding="utf-8") as f:
    dataset = list(csv.DictReader(f))

with open(BASELINE, encoding="utf-8") as f:
    baseline = list(csv.DictReader(f))

dataset.sort(key=lambda r: r["data"])


# --------------------------------------------------
# STORICO
#
# Per ogni squadra conserviamo:
# - partite
# - punti
# - gol fatti/subiti
# - avversari affrontati
# --------------------------------------------------

storico = defaultdict(lambda: {
    "partite": 0,
    "punti": 0.0,
    "gol_fatti": 0.0,
    "gol_subiti": 0.0,
    "avversari": [],
})


# --------------------------------------------------
# FORZA GREZZA
# --------------------------------------------------

def forza_grezza(storico, squadra):
    s = storico[squadra]

    if s["partite"] == 0:
        return 0.0

    punti = s["punti"] / s["partite"]
    differenza_reti = (
        s["gol_fatti"] - s["gol_subiti"]
    ) / s["partite"]

    # Indice iniziale ottenuto direttamente dai dati.
    return punti + differenza_reti


# --------------------------------------------------
# FORZA AVVERSARI
#
# Calcoliamo la forza media degli avversari già
# affrontati, usando soltanto ciò che era noto
# PRIMA della partita corrente.
# --------------------------------------------------

def forza_avversari(storico, squadra):

    avversari = storico[squadra]["avversari"]

    if not avversari:
        return 0.0

    valori = []

    for avversario in avversari:
        valori.append(
            forza_grezza(storico, avversario)
        )

    return sum(valori) / len(valori)


# --------------------------------------------------
# FORZA CORRETTA
#
# La forza viene separata in:
# 1. prestazione della squadra
# 2. difficoltà degli avversari affrontati
#
# Non vengono utilizzati risultati futuri.
# --------------------------------------------------

def forza_corretta(storico, squadra):

    s = storico[squadra]

    if s["partite"] == 0:
        return 0.0, 0.0

    punti_per_partita = (
        s["punti"] / s["partite"]
    )

    differenza_reti_per_partita = (
        s["gol_fatti"] - s["gol_subiti"]
    ) / s["partite"]

    difficolta = forza_avversari(
        storico,
        squadra
    )

    return (
        punti_per_partita - difficolta,
        differenza_reti_per_partita - difficolta
    )


# --------------------------------------------------
# FUNZIONE AGGIORNAMENTO
# --------------------------------------------------

def aggiorna(storico, squadra, avversario, gf, gs, punti):

    storico[squadra]["partite"] += 1
    storico[squadra]["punti"] += punti
    storico[squadra]["gol_fatti"] += gf
    storico[squadra]["gol_subiti"] += gs
    storico[squadra]["avversari"].append(avversario)


# --------------------------------------------------
# COSTRUZIONE DELLE FORZE PRE-PARTITA
# --------------------------------------------------

forze = {}

for r in dataset:

    data = r["data"]
    casa = r["casa"]
    ospite = r["ospite"]

    forza_casa = forza_corretta(
        storico,
        casa
    )

    forza_ospite = forza_corretta(
        storico,
        ospite
    )

    forze[(data, casa, ospite)] = {
        "forza_punti_diff":
            forza_casa[0] - forza_ospite[0],

        "forza_reti_diff":
            forza_casa[1] - forza_ospite[1],

        "difficolta_casa":
            forza_avversari(storico, casa),

        "difficolta_ospite":
            forza_avversari(storico, ospite),
    }

    gol_casa = int(float(r["gol_casa"]))
    gol_ospite = int(float(r["gol_ospite"]))

    if gol_casa > gol_ospite:
        punti_casa = 3
        punti_ospite = 0
    elif gol_casa < gol_ospite:
        punti_casa = 0
        punti_ospite = 3
    else:
        punti_casa = 1
        punti_ospite = 1

    aggiorna(
        storico,
        casa,
        ospite,
        gol_casa,
        gol_ospite,
        punti_casa
    )

    aggiorna(
        storico,
        ospite,
        casa,
        gol_ospite,
        gol_casa,
        punti_ospite
    )


# --------------------------------------------------
# PREPARAZIONE DELLE 20 PARTITE
# --------------------------------------------------

partite = []

for b in baseline:

    chiave = (
        b["data"],
        b["casa"],
        b["ospite"]
    )

    f = forze.get(chiave)

    if f is None:
        raise RuntimeError(
            f"Forza non trovata: {chiave}"
        )

    partite.append({
        "data": b["data"],
        "casa": b["casa"],
        "ospite": b["ospite"],
        "gol_casa": float(b["gol_casa_reali"]),
        "gol_ospite": float(b["gol_ospite_reali"]),
        "baseline_casa": float(b["gol_casa_attesi"]),
        "baseline_ospite": float(b["gol_ospite_attesi"]),

        "forza_punti_diff":
            f["forza_punti_diff"],

        "forza_reti_diff":
            f["forza_reti_diff"],

        "difficolta_casa":
            f["difficolta_casa"],

        "difficolta_ospite":
            f["difficolta_ospite"],
    })


# --------------------------------------------------
# MODELLO
#
# La regressione impara dai dati quale relazione
# esiste tra forza corretta e errore del baseline.
# --------------------------------------------------

X = [
    [
        p["forza_punti_diff"],
        p["forza_reti_diff"],
        p["difficolta_casa"],
        p["difficolta_ospite"],
    ]
    for p in partite
]

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
        "gol_casa_reali": attuale["gol_casa"],
        "gol_ospite_reali": attuale["gol_ospite"],
        "gol_casa_baseline": attuale["baseline_casa"],
        "gol_ospite_baseline": attuale["baseline_ospite"],
        "gol_casa_previsti": previsione_casa,
        "gol_ospite_previsti": previsione_ospite,
    })


# --------------------------------------------------
# METRICHE
# --------------------------------------------------

y_casa_reale = [
    p["gol_casa_reali"]
    for p in predizioni
]

y_casa_pred = [
    p["gol_casa_previsti"]
    for p in predizioni
]

y_ospite_reale = [
    p["gol_ospite_reali"]
    for p in predizioni
]

y_ospite_pred = [
    p["gol_ospite_previsti"]
    for p in predizioni
]

mae_casa = mean_absolute_error(
    y_casa_reale,
    y_casa_pred
)

mae_ospite = mean_absolute_error(
    y_ospite_reale,
    y_ospite_pred
)

rmse_casa = math.sqrt(
    mean_squared_error(
        y_casa_reale,
        y_casa_pred
    )
)

rmse_ospite = math.sqrt(
    mean_squared_error(
        y_ospite_reale,
        y_ospite_pred
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
print("===== BASELINE + FORZA SQUADRE 2.0 =====")
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
