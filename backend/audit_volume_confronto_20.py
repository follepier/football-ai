import csv
import math
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

FEATURES = "data/serie_a_features.csv"
BASELINE = "data/serie_a_backtest_baseline.csv"


def num(x):
    return float(x) if x not in ("", None) else None


with open(FEATURES, encoding="utf-8") as f:
    features = list(csv.DictReader(f))

with open(BASELINE, encoding="utf-8") as f:
    baseline = list(csv.DictReader(f))


idx = {
    (r["data"], r["casa"], r["ospite"]): r
    for r in features
}


rows = []

for b in baseline:
    key = (b["data"], b["casa"], b["ospite"])
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


def metric(y, p):
    mae = mean_absolute_error(y, p)
    rmse = math.sqrt(mean_squared_error(y, p))
    return mae, rmse


# ------------------------------------------------------------
# BASELINE
# ------------------------------------------------------------

yc = [r["gol_casa"] for r in rows]
yo = [r["gol_ospite"] for r in rows]

bc = [r["base_casa"] for r in rows]
bo = [r["base_ospite"] for r in rows]

mae_c, rmse_c = metric(yc, bc)
mae_o, rmse_o = metric(yo, bo)

print()
print("=" * 75)
print("AUDIT VOLUME TIRI - CONFRONTO METODOLOGICO")
print("=" * 75)
print(f"Partite: {len(rows)}")
print()
print(f"BASELINE")
print(f"MAE  = {(mae_c + mae_o)/2:.4f}")
print(f"RMSE = {(rmse_c + rmse_o)/2:.4f}")


# ------------------------------------------------------------
# WALK-FORWARD
# ------------------------------------------------------------

pred_c = []
pred_o = []

for i, r in enumerate(rows):

    if i < 3:
        pc = r["base_casa"]
        po = r["base_ospite"]

    else:

        X = [[rows[j]["volume"]] for j in range(i)]

        residual_c = [
            rows[j]["gol_casa"] - rows[j]["base_casa"]
            for j in range(i)
        ]

        residual_o = [
            rows[j]["gol_ospite"] - rows[j]["base_ospite"]
            for j in range(i)
        ]

        model_c = LinearRegression()
        model_o = LinearRegression()

        model_c.fit(X, residual_c)
        model_o.fit(X, residual_o)

        correction_c = model_c.predict(
            [[r["volume"]]]
        )[0]

        correction_o = model_o.predict(
            [[r["volume"]]]
        )[0]

        pc = max(0.0, r["base_casa"] + correction_c)
        po = max(0.0, r["base_ospite"] + correction_o)

    pred_c.append(pc)
    pred_o.append(po)


mae_c2, rmse_c2 = metric(yc, pred_c)
mae_o2, rmse_o2 = metric(yo, pred_o)

mae = (mae_c2 + mae_o2) / 2
rmse = (rmse_c2 + rmse_o2) / 2

print()
print("VOLUME TIRI - WALK FORWARD")
print(f"MAE  = {mae:.4f}")
print(f"RMSE = {rmse:.4f}")
print(f"dMAE  = {mae - ((mae_c + mae_o)/2):+.4f}")
print(f"dRMSE = {rmse - ((rmse_c + rmse_o)/2):+.4f}")


# ------------------------------------------------------------
# DETTAGLIO PARTITA PER PARTITA
# ------------------------------------------------------------

print()
print("=" * 75)
print("DETTAGLIO PREDIZIONI")
print("=" * 75)

for i, r in enumerate(rows):

    err_base = (
        abs(r["gol_casa"] - r["base_casa"])
        + abs(r["gol_ospite"] - r["base_ospite"])
    ) / 2

    err_volume = (
        abs(r["gol_casa"] - pred_c[i])
        + abs(r["gol_ospite"] - pred_o[i])
    ) / 2

    print(
        f"{i+1:02d} {r['data']} "
        f"{r['casa']} - {r['ospite']} | "
        f"tiri_diff={r['volume']:+.2f} | "
        f"base={r['base_casa']:.3f}-{r['base_ospite']:.3f} | "
        f"vol={pred_c[i]:.3f}-{pred_o[i]:.3f} | "
        f"err {err_base:.3f}->{err_volume:.3f}"
    )


# ------------------------------------------------------------
# CONTROLLI
# ------------------------------------------------------------

negative = sum(
    1 for x in pred_c + pred_o
    if x < 0
)

extreme = sum(
    1 for x in pred_c + pred_o
    if x > 4
)

print()
print("=" * 75)
print("CONTROLLI")
print("=" * 75)
print(f"Predizioni negative: {negative}")
print(f"Predizioni > 4 gol:  {extreme}")
print(
    f"Min predizione: {min(pred_c + pred_o):.4f}"
)
print(
    f"Max predizione: {max(pred_c + pred_o):.4f}"
)

print()
print("RIFERIMENTI:")
print("Baseline precedente: 0.7683 / 0.9473")
print("Volume precedente:   0.7547 / 0.9261")
print("Volume nuovo:        0.7222 / 0.8711")
print()
print("FINE AUDIT")
