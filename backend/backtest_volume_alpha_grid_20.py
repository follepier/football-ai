import csv
import math

from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error


FEATURES = "data/serie_a_features.csv"
BASELINE = "data/serie_a_backtest_baseline.csv"


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

    def n(x):
        return float(x) if x not in ("", None) else 0.0

    volume = (
        n(f["casa_tiri_in_porta_totale_pre"])
        + n(f["casa_tiri_fuori_totale_pre"])
        - n(f["ospite_tiri_in_porta_totale_pre"])
        - n(f["ospite_tiri_fuori_totale_pre"])
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


yc = [r["gol_casa"] for r in rows]
yo = [r["gol_ospite"] for r in rows]

base_c = [r["base_casa"] for r in rows]
base_o = [r["base_ospite"] for r in rows]


def metriche(y, pred):

    mae = mean_absolute_error(y, pred)

    rmse = math.sqrt(
        mean_squared_error(y, pred)
    )

    return mae, rmse


base_mae_c, base_rmse_c = metriche(yc, base_c)
base_mae_o, base_rmse_o = metriche(yo, base_o)

base_mae = (base_mae_c + base_mae_o) / 2
base_rmse = (base_rmse_c + base_rmse_o) / 2


def test_alpha(alpha):

    pred_c = []
    pred_o = []

    for i, r in enumerate(rows):

        # Le prime 3 partite non hanno storico sufficiente:
        # usiamo esclusivamente la baseline ufficiale.
        if i < 3:

            pc = r["base_casa"]
            po = r["base_ospite"]

        else:

            storico = rows[:i]

            X = [
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

            model_c = Ridge(alpha=alpha)
            model_o = Ridge(alpha=alpha)

            model_c.fit(X, y_c)
            model_o.fit(X, y_o)

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

        pred_c.append(pc)
        pred_o.append(po)

    mae_c, rmse_c = metriche(yc, pred_c)
    mae_o, rmse_o = metriche(yo, pred_o)

    mae = (mae_c + mae_o) / 2
    rmse = (rmse_c + rmse_o) / 2

    valori = pred_c + pred_o

    return {
        "alpha": alpha,
        "mae": mae,
        "rmse": rmse,
        "dmae": mae - base_mae,
        "drmse": rmse - base_rmse,
        "min": min(valori),
        "max": max(valori),
        "over3": sum(x > 3 for x in valori),
        "zero": sum(x == 0 for x in valori),
    }


alphas = [
    10,
    25,
    50,
    75,
    100,
    150,
    200,
    300,
    500,
]


print()
print("=" * 100)
print("GRID ALPHA - RIDGE VOLUME TIRI")
print("=" * 100)

print(
    f"{'Modello':12s}"
    f"{'MAE':10s}"
    f"{'RMSE':10s}"
    f"{'dMAE':10s}"
    f"{'dRMSE':10s}"
    f"{'min':10s}"
    f"{'max':10s}"
    f"{'>3':8s}"
    f"{'=0':8s}"
)

print("-" * 100)

print(
    f"{'baseline':12s}"
    f"{base_mae:10.4f}"
    f"{base_rmse:10.4f}"
    f"{0:+10.4f}"
    f"{0:+10.4f}"
    f"{min(base_c + base_o):10.4f}"
    f"{max(base_c + base_o):10.4f}"
    f"{sum(x > 3 for x in base_c + base_o):8d}"
    f"{sum(x == 0 for x in base_c + base_o):8d}"
)


risultati = []


for alpha in alphas:

    r = test_alpha(alpha)

    risultati.append(r)

    print(
        f"{'ridge' + str(alpha):12s}"
        f"{r['mae']:10.4f}"
        f"{r['rmse']:10.4f}"
        f"{r['dmae']:+10.4f}"
        f"{r['drmse']:+10.4f}"
        f"{r['min']:10.4f}"
        f"{r['max']:10.4f}"
        f"{r['over3']:8d}"
        f"{r['zero']:8d}"
    )


print()
print("=" * 100)
print("MIGLIORI MODELLI")
print("=" * 100)

validi = [
    r for r in risultati
    if r["dmae"] < 0 and r["drmse"] < 0
]

validi_mae = sorted(
    validi,
    key=lambda r: r["mae"]
)

validi_rmse = sorted(
    validi,
    key=lambda r: r["rmse"]
)


print()
print("Per MAE:")
for r in validi_mae:
    print(
        f"alpha={r['alpha']:>3} | "
        f"MAE={r['mae']:.4f} | "
        f"RMSE={r['rmse']:.4f}"
    )


print()
print("Per RMSE:")
for r in validi_rmse:
    print(
        f"alpha={r['alpha']:>3} | "
        f"MAE={r['mae']:.4f} | "
        f"RMSE={r['rmse']:.4f}"
    )


print()
print("=" * 100)
print("Nessuna modifica al modello principale.")
print("=" * 100)
