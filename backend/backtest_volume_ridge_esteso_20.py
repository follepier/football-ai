import csv
import math

from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error


FEATURES = "data/serie_a_features.csv"
BASELINE = "data/serie_a_backtest_baseline.csv"


with open(FEATURES, encoding="utf-8") as f:
    features = list(csv.DictReader(f))

with open(BASELINE, encoding="utf-8") as f:
    baseline = list(csv.DictReader(f))


features_idx = {
    (r["data"], r["casa"], r["ospite"]): r
    for r in features
}


rows = []

for b in baseline:

    key = (b["data"], b["casa"], b["ospite"])
    f = features_idx[key]

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


def valuta(pred_c, pred_o):

    mae_c = mean_absolute_error(yc, pred_c)
    mae_o = mean_absolute_error(yo, pred_o)

    rmse_c = math.sqrt(
        mean_squared_error(yc, pred_c)
    )

    rmse_o = math.sqrt(
        mean_squared_error(yo, pred_o)
    )

    mae = (mae_c + mae_o) / 2
    rmse = (rmse_c + rmse_o) / 2

    valori = pred_c + pred_o

    return (
        mae,
        rmse,
        min(valori),
        max(valori),
        sum(x > 3 for x in valori),
        sum(x == 0 for x in valori),
    )


def backtest(model_factory):

    pred_c = []
    pred_o = []

    for i, r in enumerate(rows):

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

            model_c = model_factory()
            model_o = model_factory()

            model_c.fit(X, y_c)
            model_o.fit(X, y_o)

            corr_c = model_c.predict(
                [[r["volume"]]]
            )[0]

            corr_o = model_o.predict(
                [[r["volume"]]]
            )[0]

            pc = max(
                0.0,
                r["base_casa"] + corr_c
            )

            po = max(
                0.0,
                r["base_ospite"] + corr_o
            )

        pred_c.append(pc)
        pred_o.append(po)

    return valuta(pred_c, pred_o)


# Baseline
base_mae = (
    mean_absolute_error(yc, base_c)
    + mean_absolute_error(yo, base_o)
) / 2

base_rmse = (
    math.sqrt(mean_squared_error(yc, base_c))
    + math.sqrt(mean_squared_error(yo, base_o))
) / 2


modelli = [
    ("linear", LinearRegression),
    ("ridge0.1", lambda: Ridge(alpha=0.1)),
    ("ridge1", lambda: Ridge(alpha=1.0)),
    ("ridge10", lambda: Ridge(alpha=10.0)),
    ("ridge50", lambda: Ridge(alpha=50.0)),
    ("ridge100", lambda: Ridge(alpha=100.0)),
]


print()
print("=" * 100)
print("STABILITA VOLUME TIRI - RIDGE ESTESO")
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
    f"{0:10.4f}"
    f"{0:10.4f}"
    f"{min(base_c + base_o):10.4f}"
    f"{max(base_c + base_o):10.4f}"
    f"{sum(x > 3 for x in base_c + base_o):8d}"
    f"{sum(x == 0 for x in base_c + base_o):8d}"
)


risultati = []


for nome, factory in modelli:

    mae, rmse, minimo, massimo, sopra3, zero = backtest(factory)

    dmae = mae - base_mae
    drmse = rmse - base_rmse

    risultati.append(
        (
            nome,
            mae,
            rmse,
            dmae,
            drmse,
            minimo,
            massimo,
            sopra3,
            zero,
        )
    )

    print(
        f"{nome:12s}"
        f"{mae:10.4f}"
        f"{rmse:10.4f}"
        f"{dmae:10.4f}"
        f"{drmse:10.4f}"
        f"{minimo:10.4f}"
        f"{massimo:10.4f}"
        f"{sopra3:8d}"
        f"{zero:8d}"
    )


print()
print("=" * 100)
print("MODELLI CHE MIGLIORANO SIA MAE SIA RMSE")
print("=" * 100)

validi = [
    r for r in risultati
    if r[3] < 0 and r[4] < 0
]

validi.sort(key=lambda x: (x[1], x[2]))

for r in validi:

    print(
        f"{r[0]:12s} | "
        f"MAE={r[1]:.4f} | "
        f"RMSE={r[2]:.4f} | "
        f"dMAE={r[3]:+.4f} | "
        f"dRMSE={r[4]:+.4f}"
    )


print()
print("Nessuna modifica al modello principale.")
