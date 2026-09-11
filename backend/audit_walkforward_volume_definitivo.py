import csv
import math
from pathlib import Path

from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error


ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "data" / "serie_a_features.csv"
BASELINE = ROOT / "data" / "serie_a_backtest_baseline.csv"


def num(x):
    return float(x) if x not in ("", None) else None


with FEATURES.open(encoding="utf-8") as f:
    features = list(csv.DictReader(f))

with BASELINE.open(encoding="utf-8") as f:
    baseline = list(csv.DictReader(f))

idx = {
    (r["data"], r["casa"], r["ospite"]): r
    for r in features
}

rows = []

for b in baseline:
    key = (b["data"], b["casa"], b["ospite"])
    if key not in idx:
        raise RuntimeError(f"Feature mancanti: {key}")

    f = idx[key]
    volume = (
        num(f["casa_tiri_in_porta_totale_pre"])
        + num(f["casa_tiri_fuori_totale_pre"])
        - num(f["ospite_tiri_in_porta_totale_pre"])
        - num(f["ospite_tiri_fuori_totale_pre"])
    )

    rows.append({
        "data": b["data"],
        "casa": b["casa"],
        "ospite": b["ospite"],
        "gol_casa": float(b["gol_casa_reali"]),
        "gol_ospite": float(b["gol_ospite_reali"]),
        "base_casa": float(b["gol_casa_attesi"]),
        "base_ospite": float(b["gol_ospite_attesi"]),
        "volume": volume,
    })

print("=" * 100)
print("AUDIT DEFINITIVO WALK-FORWARD VOLUME")
print("=" * 100)
print(f"Partite: {len(rows)}")

pred_a_c, pred_a_o = [], []

for i, r in enumerate(rows):
    if i < 3:
        pc, po = r["base_casa"], r["base_ospite"]
    else:
        storico = rows[:i]
        X_train = [[x["volume"]] for x in storico]
        y_c = [x["gol_casa"] - x["base_casa"] for x in storico]
        y_o = [x["gol_ospite"] - x["base_ospite"] for x in storico]

        model_c = LinearRegression().fit(X_train, y_c)
        model_o = LinearRegression().fit(X_train, y_o)
        pc = max(0.0, r["base_casa"] + model_c.predict([[r["volume"]]])[0])
        po = max(0.0, r["base_ospite"] + model_o.predict([[r["volume"]]])[0])

    pred_a_c.append(pc)
    pred_a_o.append(po)


yc = [r["gol_casa"] for r in rows]
yo = [r["gol_ospite"] for r in rows]


def metriche(y, p):
    return (
        mean_absolute_error(y, p),
        math.sqrt(mean_squared_error(y, p)),
    )


mae_c, rmse_c = metriche(yc, pred_a_c)
mae_o, rmse_o = metriche(yo, pred_a_o)
mae = (mae_c + mae_o) / 2
rmse = (rmse_c + rmse_o) / 2

print(f"Walk-forward volume: MAE={mae:.4f} RMSE={rmse:.4f}")
print(f"Home: MAE={mae_c:.4f} RMSE={rmse_c:.4f}")
print(f"Away: MAE={mae_o:.4f} RMSE={rmse_o:.4f}")
print("Nessuna modifica al modello principale.")
