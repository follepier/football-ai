import csv
import math

from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline


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

    cp = num(f["casa_tiri_in_porta_totale_pre"])
    cf = num(f["casa_tiri_fuori_totale_pre"])
    op = num(f["ospite_tiri_in_porta_totale_pre"])
    of = num(f["ospite_tiri_fuori_totale_pre"])

    volume = (cp + cf) - (op + of)

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


def valuta(pred_c, pred_o):

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
    }


def test(modello, standardizza=False):

    pred_c = []
    pred_o = []

    for i, r in enumerate(rows):

        # Prime 3 partite: nessuna correzione
        if i < 3:

            pred_c.append(r["base_casa"])
            pred_o.append(r["base_ospite"])
            continue

        X_train = [
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

        if standardizza:

            modello_c = make_pipeline(
                StandardScaler(),
                modello()
            )

            modello_o = make_pipeline(
                StandardScaler(),
                modello()
            )

        else:

            modello_c = modello()
            modello_o = modello()

        modello_c.fit(X_train, resid_c)
        modello_o.fit(X_train, resid_o)

        correction_c = modello_c.predict(
            [[r["volume"]]]
        )[0]

        correction_o = modello_o.predict(
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

    return valuta(pred_c, pred_o), pred_c, pred_o


# ============================================================
# BASELINE
# ============================================================

base_c = [r["base_casa"] for r in rows]
base_o = [r["base_ospite"] for r in rows]

baseline = valuta(base_c, base_o)


# ============================================================
# TEST MODELLI
# ============================================================

risultati = []

# Regressione lineare normale
metriche, pc, po = test(
    LinearRegression,
    standardizza=False
)

risultati.append(
    ("LinearRegression", metriche, pc, po)
)


# Ridge alpha 0.1
metriche, pc, po = test(
    lambda: Ridge(alpha=0.1),
    standardizza=False
)

risultati.append(
    ("Ridge 0.1", metriche, pc, po)
)


# Ridge alpha 1
metriche, pc, po = test(
    lambda: Ridge(alpha=1.0),
    standardizza=False
)

risultati.append(
    ("Ridge 1.0", metriche, pc, po)
)


# Ridge alpha 10
metriche, pc, po = test(
    lambda: Ridge(alpha=10.0),
    standardizza=False
)

risultati.append(
    ("Ridge 10", metriche, pc, po)
)


# Ridge + standardizzazione
metriche, pc, po = test(
    lambda: Ridge(alpha=1.0),
    standardizza=True
)

risultati.append(
    ("Ridge 1.0 + standard", metriche, pc, po)
)


# ============================================================
# OUTPUT
# ============================================================

print()
print("=" * 85)
print("STRESS TEST STABILITA VOLUME TIRI")
print("=" * 85)

print()
print(
    f"{'Modello':25s}"
    f" MAE       RMSE      dMAE      dRMSE"
)
print("-" * 85)

print(
    f"{'BASELINE':25s}"
    f" {baseline['mae']:.4f}"
    f"    {baseline['rmse']:.4f}"
    f"    +0.0000"
    f"    +0.0000"
)

for nome, m, _, _ in risultati:

    print(
        f"{nome:25s}"
        f" {m['mae']:.4f}"
        f"    {m['rmse']:.4f}"
        f"    {m['mae'] - baseline['mae']:+.4f}"
        f"    {m['rmse'] - baseline['rmse']:+.4f}"
    )


print()
print("=" * 85)
print("MIGLIORAMENTO RISPETTO AL SOLO VOLUME")
print("=" * 85)

volume_metriche = risultati[0][1]

print(
    f"Volume LinearRegression: "
    f"MAE={volume_metriche['mae']:.4f} "
    f"RMSE={volume_metriche['rmse']:.4f}"
)

for nome, m, _, _ in risultati[1:]:

    print(
        f"{nome:25s} "
        f"dMAE={m['mae'] - volume_metriche['mae']:+.4f} "
        f"dRMSE={m['rmse'] - volume_metriche['rmse']:+.4f}"
    )


# ============================================================
# PREDIZIONI ESTREME
# ============================================================

print()
print("=" * 85)
print("CONTROLLO PREDIZIONI ESTREME")
print("=" * 85)

for nome, m, pc, po in risultati:

    valori = pc + po

    print(
        f"{nome:25s} "
        f"min={min(valori):.3f} "
        f"max={max(valori):.3f} "
        f">3 gol={sum(x > 3 for x in valori)}"
    )


# ============================================================
# DETTAGLIO DEL MIGLIORE
# ============================================================

migliore = min(
    risultati,
    key=lambda x: (x[1]["mae"], x[1]["rmse"])
)

nome, m, pc, po = migliore

print()
print("=" * 85)
print(f"MIGLIORE: {nome}")
print("=" * 85)

print(
    f"MAE  = {m['mae']:.4f}"
)

print(
    f"RMSE = {m['rmse']:.4f}"
)

print(
    f"MAE casa = {m['mae_casa']:.4f}"
)

print(
    f"MAE ospite = {m['mae_ospite']:.4f}"
)

print(
    f"RMSE casa = {m['rmse_casa']:.4f}"
)

print(
    f"RMSE ospite = {m['rmse_ospite']:.4f}"
)

print()
print("Nessuna modifica al modello principale.")
