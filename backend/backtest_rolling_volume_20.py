import csv
import math

from sklearn.linear_model import LinearRegression, Ridge
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

    f = idx[(b["data"], b["casa"], b["ospite"])]

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

    rmse = math.sqrt(
        mean_squared_error(y, p)
    )

    return mae, rmse


def test(window, modello_tipo):

    pred_c = []
    pred_o = []

    for i, r in enumerate(rows):

        # Nessuna correzione finché non abbiamo
        # abbastanza partite storiche.
        if i < 3:

            pred_c.append(r["base_casa"])
            pred_o.append(r["base_ospite"])
            continue

        start = max(0, i - window)

        storico = rows[start:i]

        X = [
            [x["volume"]]
            for x in storico
        ]

        resid_c = [
            x["gol_casa"] - x["base_casa"]
            for x in storico
        ]

        resid_o = [
            x["gol_ospite"] - x["base_ospite"]
            for x in storico
        ]

        if modello_tipo == "linear":

            model_c = LinearRegression()
            model_o = LinearRegression()

        elif modello_tipo == "ridge10":

            model_c = Ridge(alpha=10.0)
            model_o = Ridge(alpha=10.0)

        else:
            raise ValueError(modello_tipo)

        # Evitiamo regressioni su campioni troppo piccoli.
        if len(storico) < 4:

            correction_c = 0.0
            correction_o = 0.0

        else:

            model_c.fit(X, resid_c)
            model_o.fit(X, resid_o)

            correction_c = model_c.predict(
                [[r["volume"]]]
            )[0]

            correction_o = model_o.predict(
                [[r["volume"]]]
            )[0]

        pred_c.append(
            max(
                0.0,
                r["base_casa"] + correction_c
            )
        )

        pred_o.append(
            max(
                0.0,
                r["base_ospite"] + correction_o
            )
        )

    yc = [r["gol_casa"] for r in rows]
    yo = [r["gol_ospite"] for r in rows]

    mae_c, rmse_c = metric(yc, pred_c)
    mae_o, rmse_o = metric(yo, pred_o)

    return {
        "mae": (mae_c + mae_o) / 2,
        "rmse": (rmse_c + rmse_o) / 2,
        "mae_casa": mae_c,
        "mae_ospite": mae_o,
        "rmse_casa": rmse_c,
        "rmse_ospite": rmse_o,
        "pred_c": pred_c,
        "pred_o": pred_o,
    }


# ============================================================
# BASELINE
# ============================================================

yc = [r["gol_casa"] for r in rows]
yo = [r["gol_ospite"] for r in rows]

bc = [r["base_casa"] for r in rows]
bo = [r["base_ospite"] for r in rows]

base_mae_c, base_rmse_c = metric(yc, bc)
base_mae_o, base_rmse_o = metric(yo, bo)

base_mae = (base_mae_c + base_mae_o) / 2
base_rmse = (base_rmse_c + base_rmse_o) / 2


# ============================================================
# TEST
# ============================================================

risultati = []

for window in [5, 7, 10, 12, 19]:

    for modello in ["linear", "ridge10"]:

        r = test(window, modello)

        risultati.append({
            "window": window,
            "modello": modello,
            **r,
        })


# ============================================================
# OUTPUT
# ============================================================

print()
print("=" * 90)
print("ROLLING WALK-FORWARD - VOLUME TIRI")
print("=" * 90)

print()
print(
    f"{'Finestra':10s}"
    f"{'Modello':15s}"
    f"{'MAE':10s}"
    f"{'RMSE':10s}"
    f"{'dMAE':10s}"
    f"{'dRMSE':10s}"
)

print("-" * 90)

print(
    f"{'Baseline':10s}"
    f"{'-':15s}"
    f"{base_mae:.4f}    "
    f"{base_rmse:.4f}    "
    f"+0.0000    "
    f"+0.0000"
)

for r in risultati:

    print(
        f"{r['window']:10d}"
        f"{r['modello']:15s}"
        f"{r['mae']:.4f}    "
        f"{r['rmse']:.4f}    "
        f"{r['mae'] - base_mae:+.4f}    "
        f"{r['rmse'] - base_rmse:+.4f}"
    )


# ============================================================
# MIGLIORI
# ============================================================

print()
print("=" * 90)
print("MODELLI CHE MIGLIORANO SIA MAE SIA RMSE")
print("=" * 90)

migliori = [
    r for r in risultati
    if r["mae"] < base_mae
    and r["rmse"] < base_rmse
]

migliori.sort(
    key=lambda r: (r["mae"], r["rmse"])
)

if migliori:

    for r in migliori:

        print(
            f"Finestra={r['window']:2d} "
            f"{r['modello']:8s} | "
            f"MAE={r['mae']:.4f} "
            f"RMSE={r['rmse']:.4f}"
        )

else:

    print("Nessun modello migliora entrambi.")


# ============================================================
# CONTROLLO ESTREMI
# ============================================================

print()
print("=" * 90)
print("CONTROLLO ESTREMI")
print("=" * 90)

for r in risultati:

    valori = r["pred_c"] + r["pred_o"]

    print(
        f"Finestra={r['window']:2d} "
        f"{r['modello']:8s} | "
        f"min={min(valori):.3f} "
        f"max={max(valori):.3f} "
        f">3={sum(x > 3 for x in valori)}"
    )


print()
print("Nessuna modifica al modello principale.")
