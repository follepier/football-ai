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


def mae(y, p):
    return sum(abs(a - b) for a, b in zip(y, p)) / len(y)


def rmse(y, p):
    return math.sqrt(
        sum((a - b) ** 2 for a, b in zip(y, p)) / len(y)
    )


def valuta(indices, pred_c, pred_o):

    yc = [rows[i]["gol_casa"] for i in indices]
    yo = [rows[i]["gol_ospite"] for i in indices]

    pc = [pred_c[i] for i in indices]
    po = [pred_o[i] for i in indices]

    mae_c = mae(yc, pc)
    mae_o = mae(yo, po)

    rmse_c = rmse(yc, pc)
    rmse_o = rmse(yo, po)

    return {
        "mae": (mae_c + mae_o) / 2,
        "rmse": (rmse_c + rmse_o) / 2,
        "mae_casa": mae_c,
        "mae_ospite": mae_o,
        "rmse_casa": rmse_c,
        "rmse_ospite": rmse_o,
    }


def genera_predizioni(tipo):

    pred_c = []
    pred_o = []

    for i, r in enumerate(rows):

        # Nessun dato futuro:
        # le prime 3 partite restano baseline.
        if i < 3:
            pred_c.append(r["base_casa"])
            pred_o.append(r["base_ospite"])
            continue

        X = [
            [rows[j]["volume"]]
            for j in range(i)
        ]

        resid_c = [
            rows[j]["gol_casa"] - rows[j]["base_casa"]
            for j in range(i)
        ]

        resid_o = [
            rows[j]["gol_ospite"] - rows[j]["base_ospite"]
            for j in range(i)
        ]

        if tipo == "linear":
            model_c = LinearRegression()
            model_o = LinearRegression()

        elif tipo == "ridge10":
            model_c = Ridge(alpha=10.0)
            model_o = Ridge(alpha=10.0)

        else:
            raise ValueError(tipo)

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

    return pred_c, pred_o


# ============================================================
# PREDIZIONI
# ============================================================

baseline_c = [r["base_casa"] for r in rows]
baseline_o = [r["base_ospite"] for r in rows]

linear_c, linear_o = genera_predizioni("linear")
ridge_c, ridge_o = genera_predizioni("ridge10")


# ============================================================
# PERIODI
# ============================================================

periodi = {
    "Prime 6": list(range(0, 6)),
    "Centrale 7-13": list(range(6, 13)),
    "Ultime 7": list(range(13, 20)),
    "Tutte": list(range(20)),
}


print()
print("=" * 95)
print("STABILITA TEMPORALE - VOLUME TIRI")
print("=" * 95)

print()
print(
    f"{'Periodo':18s}"
    f"{'Baseline MAE':14s}"
    f"{'Ridge10 MAE':14s}"
    f"{'dMAE':10s}"
    f"{'Baseline RMSE':16s}"
    f"{'Ridge10 RMSE':15s}"
    f"{'dRMSE':10s}"
)

print("-" * 95)


for nome, indici in periodi.items():

    base = valuta(
        indici,
        baseline_c,
        baseline_o
    )

    ridge = valuta(
        indici,
        ridge_c,
        ridge_o
    )

    print(
        f"{nome:18s}"
        f"{base['mae']:.4f}        "
        f"{ridge['mae']:.4f}        "
        f"{ridge['mae'] - base['mae']:+.4f}    "
        f"{base['rmse']:.4f}          "
        f"{ridge['rmse']:.4f}         "
        f"{ridge['rmse'] - base['rmse']:+.4f}"
    )


# ============================================================
# CONFRONTO PARTITA PER PARTITA
# ============================================================

migliora_mae_ridge = 0
peggiora_mae_ridge = 0

migliora_rmse_ridge = 0
peggiora_rmse_ridge = 0

migliora_entrambe = 0


print()
print("=" * 95)
print("CONFRONTO PARTITA PER PARTITA - RIDGE 10")
print("=" * 95)

print()
print(
    f"{'#':3s}"
    f"{'Partita':32s}"
    f"{'Err Base':10s}"
    f"{'Err Ridge':11s}"
    f"{'Delta':10s}"
    f"{'Esito':10s}"
)

print("-" * 95)


for i, r in enumerate(rows):

    err_base = (
        abs(r["gol_casa"] - baseline_c[i])
        + abs(r["gol_ospite"] - baseline_o[i])
    ) / 2

    err_ridge = (
        abs(r["gol_casa"] - ridge_c[i])
        + abs(r["gol_ospite"] - ridge_o[i])
    ) / 2

    delta = err_ridge - err_base

    if delta < 0:
        migliora_mae_ridge += 1
        esito = "MIGLIORA"

    elif delta > 0:
        peggiora_mae_ridge += 1
        esito = "PEGGIORA"

    else:
        esito = "UGUALE"

    # Per questa analisi usiamo la stessa metrica
    # assoluta per il confronto partita-per-partita.
    if delta < 0:
        migliora_rmse_ridge += 1
    elif delta > 0:
        peggiora_rmse_ridge += 1

    if delta < 0:
        migliora_entrambe += 1

    print(
        f"{i+1:02d} "
        f"{r['casa']} - {r['ospite']:20s} "
        f"{err_base:.3f}     "
        f"{err_ridge:.3f}      "
        f"{delta:+.3f}     "
        f"{esito}"
    )


# ============================================================
# RISULTATO FINALE
# ============================================================

base_all = valuta(
    list(range(20)),
    baseline_c,
    baseline_o
)

linear_all = valuta(
    list(range(20)),
    linear_c,
    linear_o
)

ridge_all = valuta(
    list(range(20)),
    ridge_c,
    ridge_o
)


print()
print("=" * 95)
print("RISULTATO FINALE")
print("=" * 95)

print()
print(
    f"Baseline       MAE={base_all['mae']:.4f} "
    f"RMSE={base_all['rmse']:.4f}"
)

print(
    f"Volume Linear  MAE={linear_all['mae']:.4f} "
    f"RMSE={linear_all['rmse']:.4f}"
)

print(
    f"Volume Ridge10 MAE={ridge_all['mae']:.4f} "
    f"RMSE={ridge_all['rmse']:.4f}"
)

print()
print(
    f"Ridge10 vs baseline:"
    f" dMAE={ridge_all['mae'] - base_all['mae']:+.4f}"
    f" dRMSE={ridge_all['rmse'] - base_all['rmse']:+.4f}"
)

print()
print(
    f"Partite migliorate: {migliora_mae_ridge}"
)

print(
    f"Partite peggiorate: {peggiora_mae_ridge}"
)

print()
print("Nessuna modifica al modello principale.")
