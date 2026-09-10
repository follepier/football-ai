import csv
from collections import defaultdict
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

DATASET = "../data/serie_a_dataset.csv"
BASELINE = "../data/serie_a_backtest_baseline.csv"
OUTPUT = "../data/serie_a_backtest_baseline_forza_20.csv"


def aggiorna_storico(storico, squadra, gf, gs, punti):
    storico[squadra]["partite"] += 1
    storico[squadra]["punti"] += punti
    storico[squadra]["gol_fatti"] += gf
    storico[squadra]["gol_subiti"] += gs


def forza(storico, squadra):
    s = storico[squadra]

    if s["partite"] == 0:
        return 0.0, 0.0

    punti_per_partita = s["punti"] / s["partite"]

    differenza_reti_per_partita = (
        s["gol_fatti"] - s["gol_subiti"]
    ) / s["partite"]

    return punti_per_partita, differenza_reti_per_partita


# --------------------------------------------------
# CARICAMENTO DATASET
# --------------------------------------------------

with open(DATASET, encoding="utf-8") as f:
    dataset = list(csv.DictReader(f))

with open(BASELINE, encoding="utf-8") as f:
    baseline = list(csv.DictReader(f))


dataset.sort(key=lambda r: r["data"])


# --------------------------------------------------
# COSTRUZIONE DELLE FORZE PRE-PARTITA
# --------------------------------------------------

storico = defaultdict(lambda: {
    "partite": 0,
    "punti": 0,
    "gol_fatti": 0,
    "gol_subiti": 0,
})

for r in dataset:

    casa = r["casa"]
    ospite = r["ospite"]

    forza_casa = forza(storico, casa)
    forza_ospite = forza(storico, ospite)

    r["forza_punti_diff"] = (
        forza_casa[0] - forza_ospite[0]
    )

    r["forza_reti_diff"] = (
        forza_casa[1] - forza_ospite[1]
    )

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

    aggiorna_storico(
        storico,
        casa,
        gol_casa,
        gol_ospite,
        punti_casa
    )

    aggiorna_storico(
        storico,
        ospite,
        gol_ospite,
        gol_casa,
        punti_ospite
    )


# --------------------------------------------------
# RICOSTRUZIONE CORRETTA DELLO STORICO
#
# Questo secondo passaggio salva la forza associata
# a ogni partita PRIMA che essa venga giocata.
# --------------------------------------------------

storico = defaultdict(lambda: {
    "partite": 0,
    "punti": 0,
    "gol_fatti": 0,
    "gol_subiti": 0,
})

for r in dataset:

    casa = r["casa"]
    ospite = r["ospite"]

    forza_casa = forza(storico, casa)
    forza_ospite = forza(storico, ospite)

    r["forza_punti_diff"] = (
        forza_casa[0] - forza_ospite[0]
    )

    r["forza_reti_diff"] = (
        forza_casa[1] - forza_ospite[1]
    )

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

    aggiorna_storico(
        storico,
        casa,
        gol_casa,
        gol_ospite,
        punti_casa
    )

    aggiorna_storico(
        storico,
        ospite,
        gol_ospite,
        gol_casa,
        punti_ospite
    )


# --------------------------------------------------
# INDICE DELLE FORZE
# --------------------------------------------------

forza_indice = {
    (
        r["data"],
        r["casa"],
        r["ospite"]
    ): {
        "forza_punti_diff": r["forza_punti_diff"],
        "forza_reti_diff": r["forza_reti_diff"],
    }
    for r in dataset
}


# --------------------------------------------------
# PREPARAZIONE DELLE 20 PARTITE DEL BASELINE
# --------------------------------------------------

partite = []

for b in baseline:

    chiave = (
        b["data"],
        b["casa"],
        b["ospite"]
    )

    f = forza_indice.get(chiave)

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
        "forza_punti_diff": f["forza_punti_diff"],
        "forza_reti_diff": f["forza_reti_diff"],
    })


# --------------------------------------------------
# MODELLO
# --------------------------------------------------

X = [
    [
        p["forza_punti_diff"],
        p["forza_reti_diff"],
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

    modello_casa.fit(X_train, yc_train)
    modello_ospite.fit(X_train, yo_train)

    X_test = [X[i]]

    correzione_casa = float(
        modello_casa.predict(X_test)[0]
    )

    correzione_ospite = float(
        modello_ospite.predict(X_test)[0]
    )

    pred_casa = max(
        0.0,
        attuale["baseline_casa"] + correzione_casa
    )

    pred_ospite = max(
        0.0,
        attuale["baseline_ospite"] + correzione_ospite
    )

    predizioni.append({
        "data": attuale["data"],
        "casa": attuale["casa"],
        "ospite": attuale["ospite"],
        "gol_casa_reali": attuale["gol_casa"],
        "gol_ospite_reali": attuale["gol_ospite"],
        "baseline_casa": attuale["baseline_casa"],
        "baseline_ospite": attuale["baseline_ospite"],
        "forza_punti_diff": attuale["forza_punti_diff"],
        "forza_reti_diff": attuale["forza_reti_diff"],
        "gol_casa_attesi": round(pred_casa, 4),
        "gol_ospite_attesi": round(pred_ospite, 4),
    })


# --------------------------------------------------
# SALVATAGGIO
# --------------------------------------------------

with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=predizioni[0].keys()
    )
    writer.writeheader()
    writer.writerows(predizioni)


# --------------------------------------------------
# METRICHE
# --------------------------------------------------

yc = [p["gol_casa_reali"] for p in predizioni]
yo = [p["gol_ospite_reali"] for p in predizioni]

pc = [p["gol_casa_attesi"] for p in predizioni]
po = [p["gol_ospite_attesi"] for p in predizioni]

mae_casa = mean_absolute_error(yc, pc)
mae_ospite = mean_absolute_error(yo, po)

rmse_casa = mean_squared_error(yc, pc) ** 0.5
rmse_ospite = mean_squared_error(yo, po) ** 0.5

mae_medio = (mae_casa + mae_ospite) / 2
rmse_medio = (rmse_casa + rmse_ospite) / 2


print("\n===== BASELINE + FORZA SQUADRE =====")
print(f"Partite utilizzate: {len(predizioni)}")

print(f"MAE gol casa: {mae_casa:.4f}")
print(f"MAE gol ospite: {mae_ospite:.4f}")
print(f"MAE medio: {mae_medio:.4f}")

print(f"RMSE gol casa: {rmse_casa:.4f}")
print(f"RMSE gol ospite: {rmse_ospite:.4f}")
print(f"RMSE medio: {rmse_medio:.4f}")

print("\n===== CONFRONTO =====")
print("Baseline MAE medio:  0.7683")
print(f"Nuovo MAE medio:      {mae_medio:.4f}")
print(f"Differenza MAE:       {mae_medio - 0.7683:+.4f}")

print("Baseline RMSE medio: 0.9473")
print(f"Nuovo RMSE medio:     {rmse_medio:.4f}")
print(f"Differenza RMSE:      {rmse_medio - 0.9473:+.4f}")

print(f"\nFile salvato: {OUTPUT}")
