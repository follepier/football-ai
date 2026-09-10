import csv
import math
from pathlib import Path

from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

FEATURES = Path("data/serie_a_features.csv")
BASELINE = Path("data/serie_a_backtest_baseline.csv")
OUTPUT = Path("data/serie_a_volume_tiri_diff_walkforward_20.csv")


def num(x):
    if x is None or x == "":
        return 0.0
    return float(x)


def chiave(r):
    return (
        r["data"].strip(),
        r["casa"].strip(),
        r["ospite"].strip(),
    )


# ------------------------------------------------------------
# CARICAMENTO DATI
# ------------------------------------------------------------

with FEATURES.open(newline="", encoding="utf-8") as f:
    features = list(csv.DictReader(f))

with BASELINE.open(newline="", encoding="utf-8") as f:
    baseline = list(csv.DictReader(f))


# ------------------------------------------------------------
# COSTRUZIONE VOLUME TIRI
# IDENTICO AL TEST ORIGINALE
# ------------------------------------------------------------

indice = {}

for r in features:
    casa_tiri = (
        num(r["casa_tiri_in_porta_totale_pre"])
        + num(r["casa_tiri_fuori_totale_pre"])
    )

    ospite_tiri = (
        num(r["ospite_tiri_in_porta_totale_pre"])
        + num(r["ospite_tiri_fuori_totale_pre"])
    )

    indice[chiave(r)] = casa_tiri - ospite_tiri


# ------------------------------------------------------------
# BENCHMARK
# ------------------------------------------------------------

rows = []

for r in baseline:
    k = chiave(r)

    if k not in indice:
        raise SystemExit(f"Feature mancante: {k}")

    rows.append({
        "data": r["data"],
        "casa": r["casa"],
        "ospite": r["ospite"],
        "gol_casa": num(r["gol_casa_reali"]),
        "gol_ospite": num(r["gol_ospite_reali"]),
        "base_casa": num(r["gol_casa_attesi"]),
        "base_ospite": num(r["gol_ospite_attesi"]),
        "volume_diff": indice[k],
    })


# ------------------------------------------------------------
# WALK-FORWARD
#
# La partita i viene prevista usando SOLO 0..i-1.
#
# Con meno di 3 partite precedenti:
# utilizziamo semplicemente la baseline.
# ------------------------------------------------------------

pred_casa = []
pred_ospite = []

numero_correzioni = 0

for i in range(len(rows)):

    base_casa = rows[i]["base_casa"]
    base_ospite = rows[i]["base_ospite"]

    # Non abbiamo abbastanza storico per stimare
    # una relazione affidabile.
    if i < 3:
        pred_casa.append(base_casa)
        pred_ospite.append(base_ospite)
        continue

    X_train = [
        [rows[j]["volume_diff"]]
        for j in range(i)
    ]

    residui_casa = [
        rows[j]["gol_casa"] - rows[j]["base_casa"]
        for j in range(i)
    ]

    residui_ospite = [
        rows[j]["gol_ospite"] - rows[j]["base_ospite"]
        for j in range(i)
    ]

    modello_casa = LinearRegression()
    modello_ospite = LinearRegression()

    modello_casa.fit(X_train, residui_casa)
    modello_ospite.fit(X_train, residui_ospite)

    x_test = [[rows[i]["volume_diff"]]]

    correzione_casa = float(
        modello_casa.predict(x_test)[0]
    )

    correzione_ospite = float(
        modello_ospite.predict(x_test)[0]
    )

    pred_casa.append(
        base_casa + correzione_casa
    )

    pred_ospite.append(
        base_ospite + correzione_ospite
    )

    numero_correzioni += 1


# ------------------------------------------------------------
# BASELINE
# ------------------------------------------------------------

reali_casa = [r["gol_casa"] for r in rows]
reali_ospite = [r["gol_ospite"] for r in rows]

baseline_casa = [r["base_casa"] for r in rows]
baseline_ospite = [r["base_ospite"] for r in rows]


def metriche(ph, pa):
    mae_casa = mean_absolute_error(reali_casa, ph)
    mae_ospite = mean_absolute_error(reali_ospite, pa)

    rmse_casa = math.sqrt(
        mean_squared_error(reali_casa, ph)
    )

    rmse_ospite = math.sqrt(
        mean_squared_error(reali_ospite, pa)
    )

    return {
        "mae_casa": mae_casa,
        "mae_ospite": mae_ospite,
        "mae_medio": (mae_casa + mae_ospite) / 2,
        "rmse_casa": rmse_casa,
        "rmse_ospite": rmse_ospite,
        "rmse_medio": (rmse_casa + rmse_ospite) / 2,
    }


m_base = metriche(
    baseline_casa,
    baseline_ospite
)

m_volume = metriche(
    pred_casa,
    pred_ospite
)


# ------------------------------------------------------------
# RISULTATI
# ------------------------------------------------------------

print("=" * 70)
print("VOLUME TIRI DIFFERENZA - WALK-FORWARD PURO")
print("=" * 70)

print(f"Partite benchmark: {len(rows)}")
print(f"Partite con correzione: {numero_correzioni}")

print()
print("=" * 70)
print("BASELINE")
print("=" * 70)

print(f"MAE casa:     {m_base['mae_casa']:.4f}")
print(f"MAE ospite:   {m_base['mae_ospite']:.4f}")
print(f"MAE medio:    {m_base['mae_medio']:.4f}")
print(f"RMSE casa:    {m_base['rmse_casa']:.4f}")
print(f"RMSE ospite:  {m_base['rmse_ospite']:.4f}")
print(f"RMSE medio:   {m_base['rmse_medio']:.4f}")

print()
print("=" * 70)
print("BASELINE + VOLUME TIRI DIFFERENZA")
print("WALK-FORWARD")
print("=" * 70)

print(f"MAE casa:     {m_volume['mae_casa']:.4f}")
print(f"MAE ospite:   {m_volume['mae_ospite']:.4f}")
print(f"MAE medio:    {m_volume['mae_medio']:.4f}")
print(f"RMSE casa:    {m_volume['rmse_casa']:.4f}")
print(f"RMSE ospite:  {m_volume['rmse_ospite']:.4f}")
print(f"RMSE medio:   {m_volume['rmse_medio']:.4f}")

print()
print("=" * 70)
print("CONFRONTO")
print("=" * 70)

delta_mae = m_volume["mae_medio"] - m_base["mae_medio"]
delta_rmse = m_volume["rmse_medio"] - m_base["rmse_medio"]

print(f"Delta MAE medio : {delta_mae:+.4f}")
print(f"Delta RMSE medio: {delta_rmse:+.4f}")

if delta_mae < 0 and delta_rmse < 0:
    print()
    print(">>> RISULTATO MOLTO INTERESSANTE <<<")
    print(">>> MIGLIORANO SIA MAE CHE RMSE <<<")
elif delta_mae < 0:
    print()
    print(">>> MIGLIORA SOLO IL MAE <<<")
elif delta_rmse < 0:
    print()
    print(">>> MIGLIORA SOLO L'RMSE <<<")
else:
    print()
    print(">>> NESSUN MIGLIORAMENTO <<<")


# ------------------------------------------------------------
# DETTAGLIO PARTITA PER PARTITA
# ------------------------------------------------------------

print()
print("=" * 70)
print("DETTAGLIO")
print("=" * 70)

for i, r in enumerate(rows):
    print(
        f"{i+1:02d} | "
        f"{r['casa']} - {r['ospite']} | "
        f"gol={r['gol_casa']:.0f}-{r['gol_ospite']:.0f} | "
        f"base={r['base_casa']:.3f}-{r['base_ospite']:.3f} | "
        f"diff_tiri={r['volume_diff']:+.1f} | "
        f"modello={pred_casa[i]:.3f}-{pred_ospite[i]:.3f}"
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
        "volume_tiri_diff",
        "pred_casa_walkforward",
        "pred_ospite_walkforward",
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
            r["volume_diff"],
            pred_casa[i],
            pred_ospite[i],
        ])

print()
print(f"File salvato: {OUTPUT}")
print("Baseline.py NON modificato.")
print("Dataset principali NON modificati.")
