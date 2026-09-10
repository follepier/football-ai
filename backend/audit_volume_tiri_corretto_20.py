import csv
import math
from pathlib import Path

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

FEATURES = Path("data/serie_a_features.csv")
BASELINE = Path("data/serie_a_backtest_baseline.csv")
OUTPUT = Path("data/serie_a_audit_volume_tiri_20.csv")


def num(x):
    if x is None or x == "":
        return 0.0
    return float(x)


def load_features():
    with FEATURES.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_baseline():
    with BASELINE.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def chiave(r):
    return (
        r["data"].strip(),
        r["casa"].strip(),
        r["ospite"].strip(),
    )


features = load_features()
baseline = load_baseline()

# ------------------------------------------------------------
# INDICE DELLE FEATURE
# ------------------------------------------------------------

indice = {}

for r in features:
    casa_tiri_porta = num(r["casa_tiri_in_porta_totale_pre"])
    casa_tiri_fuori = num(r["casa_tiri_fuori_totale_pre"])

    ospite_tiri_porta = num(r["ospite_tiri_in_porta_totale_pre"])
    ospite_tiri_fuori = num(r["ospite_tiri_fuori_totale_pre"])

    casa_tiri = casa_tiri_porta + casa_tiri_fuori
    ospite_tiri = ospite_tiri_porta + ospite_tiri_fuori

    indice[chiave(r)] = {
        # IDENTICO AL VECCHIO TEST:
        # una sola variabile = differenza casa - ospite
        "volume_tiri": casa_tiri - ospite_tiri,

        # Conserviamo anche i valori originali per controllo
        "tiri_casa": casa_tiri,
        "tiri_ospite": ospite_tiri,
    }


# ------------------------------------------------------------
# COSTRUZIONE BENCHMARK
# ------------------------------------------------------------

rows = []

for r in baseline:
    k = chiave(r)

    if k not in indice:
        raise SystemExit(
            f"Feature mancanti per partita: {k}"
        )

    f = indice[k]

    rows.append({
        "data": r["data"],
        "casa": r["casa"],
        "ospite": r["ospite"],
        "gol_casa": num(r["gol_casa_reali"]),
        "gol_ospite": num(r["gol_ospite_reali"]),
        "base_casa": num(r["gol_casa_attesi"]),
        "base_ospite": num(r["gol_ospite_attesi"]),
        "volume_tiri": f["volume_tiri"],
        "tiri_casa": f["tiri_casa"],
        "tiri_ospite": f["tiri_ospite"],
    })


print("=" * 70)
print("AUDIT VOLUME TIRI - METODO ORIGINALE")
print("=" * 70)

print(f"Partite benchmark: {len(rows)}")

# ------------------------------------------------------------
# METODO LEAVE-ONE-OUT ORIGINALE
# ------------------------------------------------------------

y_casa = [r["gol_casa"] for r in rows]
y_ospite = [r["gol_ospite"] for r in rows]

base_casa = [r["base_casa"] for r in rows]
base_ospite = [r["base_ospite"] for r in rows]

X = [[r["volume_tiri"]] for r in rows]

pred_casa_loo = []
pred_ospite_loo = []

for i in range(len(rows)):
    X_train = X[:i] + X[i + 1:]

    yc_train = y_casa[:i] + y_casa[i + 1:]
    yo_train = y_ospite[:i] + y_ospite[i + 1:]

    # Residuo rispetto alla baseline
    rc_train = [
        yc_train[j] - (
            base_casa[:i] + base_casa[i + 1:]
        )[j]
        for j in range(len(yc_train))
    ]

    ro_train = [
        yo_train[j] - (
            base_ospite[:i] + base_ospite[i + 1:]
        )[j]
        for j in range(len(yo_train))
    ]

    modello_casa = LinearRegression()
    modello_ospite = LinearRegression()

    modello_casa.fit(X_train, rc_train)
    modello_ospite.fit(X_train, ro_train)

    correzione_casa = float(
        modello_casa.predict([X[i]])[0]
    )

    correzione_ospite = float(
        modello_ospite.predict([X[i]])[0]
    )

    pred_casa_loo.append(
        base_casa[i] + correzione_casa
    )

    pred_ospite_loo.append(
        base_ospite[i] + correzione_ospite
    )


def calcola_metriche(ph, pa):
    mae_h = mean_absolute_error(y_casa, ph)
    mae_a = mean_absolute_error(y_ospite, pa)

    rmse_h = math.sqrt(
        mean_squared_error(y_casa, ph)
    )

    rmse_a = math.sqrt(
        mean_squared_error(y_ospite, pa)
    )

    return (
        mae_h,
        mae_a,
        (mae_h + mae_a) / 2,
        rmse_h,
        rmse_a,
        (rmse_h + rmse_a) / 2,
    )


base_metrics = calcola_metriche(
    base_casa,
    base_ospite
)

loo_metrics = calcola_metriche(
    pred_casa_loo,
    pred_ospite_loo
)

print()
print("=" * 70)
print("BASELINE")
print("=" * 70)

print(f"MAE casa:     {base_metrics[0]:.4f}")
print(f"MAE ospite:   {base_metrics[1]:.4f}")
print(f"MAE medio:    {base_metrics[2]:.4f}")
print(f"RMSE casa:    {base_metrics[3]:.4f}")
print(f"RMSE ospite:  {base_metrics[4]:.4f}")
print(f"RMSE medio:   {base_metrics[5]:.4f}")

print()
print("=" * 70)
print("VOLUME TIRI - LEAVE-ONE-OUT")
print("=" * 70)

print(f"MAE casa:     {loo_metrics[0]:.4f}")
print(f"MAE ospite:   {loo_metrics[1]:.4f}")
print(f"MAE medio:    {loo_metrics[2]:.4f}")
print(f"RMSE casa:    {loo_metrics[3]:.4f}")
print(f"RMSE ospite:  {loo_metrics[4]:.4f}")
print(f"RMSE medio:   {loo_metrics[5]:.4f}")

print()
print("=" * 70)
print("CONFRONTO")
print("=" * 70)

delta_mae = loo_metrics[2] - base_metrics[2]
delta_rmse = loo_metrics[5] - base_metrics[5]

print(f"Delta MAE medio : {delta_mae:+.4f}")
print(f"Delta RMSE medio: {delta_rmse:+.4f}")

if delta_mae < 0 and delta_rmse < 0:
    print(">>> MAE E RMSE MIGLIORANO <<<")
elif delta_mae < 0:
    print(">>> SOLO MAE MIGLIORA <<<")
elif delta_rmse < 0:
    print(">>> SOLO RMSE MIGLIORA <<<")
else:
    print(">>> NESSUN MIGLIORAMENTO <<<")


# ------------------------------------------------------------
# CONTROLLO DATI
# ------------------------------------------------------------

print()
print("=" * 70)
print("CONTROLLO VOLUME TIRI")
print("=" * 70)

for r in rows:
    print(
        f"{r['data']} | "
        f"{r['casa']} - {r['ospite']} | "
        f"casa={r['tiri_casa']:.1f} "
        f"ospite={r['tiri_ospite']:.1f} "
        f"diff={r['volume_tiri']:.1f}"
    )


# ------------------------------------------------------------
# SALVATAGGIO
# ------------------------------------------------------------

with OUTPUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)

    writer.writerow([
        "data",
        "casa",
        "ospite",
        "gol_casa",
        "gol_ospite",
        "base_casa",
        "base_ospite",
        "tiri_casa",
        "tiri_ospite",
        "volume_tiri",
        "pred_casa_loo",
        "pred_ospite_loo",
    ])

    for i, r in enumerate(rows):
        writer.writerow([
            r["data"],
            r["casa"],
            r["ospite"],
            r["gol_casa"],
            r["gol_ospite"],
            r["base_casa"],
            r["base_ospite"],
            r["tiri_casa"],
            r["tiri_ospite"],
            r["volume_tiri"],
            pred_casa_loo[i],
            pred_ospite_loo[i],
        ])

print()
print("=" * 70)
print("FILE SALVATO")
print("=" * 70)
print(OUTPUT)
print("Il modello principale NON è stato modificato.")
