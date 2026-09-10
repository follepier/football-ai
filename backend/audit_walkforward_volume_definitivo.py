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


print()
print("=" * 100)
print("AUDIT DEFINITIVO WALK-FORWARD VOLUME")
print("=" * 100)

print(f"Partite: {len(rows)}")


# ============================================================
# METODO A
# WALK-FORWARD UFFICIALE
# ============================================================

pred_a_c = []
pred_a_o = []


for i, r in enumerate(rows):

    if i < 3:

        pc = r["base_casa"]
        po = r["base_ospite"]

    else:

        X_train = [
            [rows[j]["volume"]]
            for j in range(i)
        ]

        y_c = [
            rows[j]["gol_casa"] - rows[j]["base_casa"]
            for j in range(i)
        ]

        y_o = [
            rows[j]["gol_ospite"] - rows[j]["base_ospite"]
            for j in range(i)
        ]

        model_c = LinearRegression()
        model_o = LinearRegression()

        model_c.fit(X_train, y_c)
        model_o.fit(X_train, y_o)

        correction_c = model_c.predict(
            [[r["volume"]]]
        )[0]

        correction_o = model_o.predict(
            [[r["volume"]]]
        )[0]

        pc = max(
            0.0,
            r["base_casa"] + correction_c
        )

        po = max(
            0.0,
            r["base_ospite"] + correction_o
        )

    pred_a_c.append(pc)
    pred_a_o.append(po)


# ============================================================
# METODO B
# ROLLING WINDOW 19
# ============================================================

pred_b_c = []
pred_b_o = []


for i, r in enumerate(rows):

    if i < 3:

        pc = r["base_casa"]
        po = r["base_ospite"]

    else:

        start = max(0, i - 19)

        storico = rows[start:i]

        X_train = [
            [x["volume"]]
            for x in storico
        ]

        y_c = [
            x["gol_casa"] - x["base_casa"]
            for x in storico
        ]

        y_o = [
            x["gol_ospite"] - x["base_ospite"]
            for x in storico
        ]

        model_c = LinearRegression()
        model_o = LinearRegression()

        model_c.fit(X_train, y_c)
        model_o.fit(X_train, y_o)

        correction_c = model_c.predict(
            [[r["volume"]]]
        )[0]

        correction_o = model_o.predict(
            [[r["volume"]]]
        )[0]

        pc = max(
            0.0,
            r["base_casa"] + correction_c
        )

        po = max(
            0.0,
            r["base_ospite"] + correction_o
        )

    pred_b_c.append(pc)
    pred_b_o.append(po)


# ============================================================
# CONFRONTO PREDIZIONI
# ============================================================

differenze = 0

print()
print("=" * 100)
print("CONFRONTO METODO A vs METODO B")
print("=" * 100)

print(
    f"{'#':3s}"
    f"{'Partita':32s}"
    f"{'A casa':10s}"
    f"{'B casa':10s}"
    f"{'A osp':10s}"
    f"{'B osp':10s}"
    f"{'Diff':10s}"
)

print("-" * 100)


for i, r in enumerate(rows):

    diff = max(
        abs(pred_a_c[i] - pred_b_c[i]),
        abs(pred_a_o[i] - pred_b_o[i])
    )

    if diff > 1e-9:
        differenze += 1

    print(
        f"{i+1:02d} "
        f"{r['casa']} - {r['ospite']:20s} "
        f"{pred_a_c[i]:.4f}   "
        f"{pred_b_c[i]:.4f}   "
        f"{pred_a_o[i]:.4f}   "
        f"{pred_b_o[i]:.4f}   "
        f"{diff:.6f}"
    )


# ============================================================
# METRICHE
# ============================================================

yc = [r["gol_casa"] for r in rows]
yo = [r["gol_ospite"] for r in rows]


def metriche(y, p):

    mae = mean_absolute_error(y, p)

    rmse = math.sqrt(
        mean_squared_error(y, p)
    )

    return mae, rmse


a_mae_c, a_rmse_c = metriche(yc, pred_a_c)
a_mae_o, a_rmse_o = metriche(yo, pred_a_o)

b_mae_c, b_rmse_c = metriche(yc, pred_b_c)
b_mae_o, b_rmse_o = metriche(yo, pred_b_o)


a_mae = (a_mae_c + a_mae_o) / 2
a_rmse = (a_rmse_c + a_rmse_o) / 2

b_mae = (b_mae_c + b_mae_o) / 2
b_rmse = (b_rmse_c + b_rmse_o) / 2


print()
print("=" * 100)
print("RISULTATI")
print("=" * 100)

print(
    f"Metodo A - walk-forward ufficiale:"
    f" MAE={a_mae:.4f}"
    f" RMSE={a_rmse:.4f}"
)

print(
    f"Metodo B - rolling 19:"
    f" MAE={b_mae:.4f}"
    f" RMSE={b_rmse:.4f}"
)

print()
print(f"Partite con predizioni differenti: {differenze}")

if differenze == 0:
    print()
    print("OK: i due metodi sono IDENTICI.")
else:
    print()
    print("ATTENZIONE: i due metodi NON sono identici.")


# ============================================================
# CONTROLLO ORDINE TEMPORALE
# ============================================================

print()
print("=" * 100)
print("CONTROLLO ORDINE")
print("=" * 100)

for i, r in enumerate(rows):

    print(
        f"{i+1:02d} | "
        f"{r['data']} | "
        f"{r['casa']} - {r['ospite']} | "
        f"volume={r['volume']:+.2f}"
    )


print()
print("Nessuna modifica al modello principale.")
