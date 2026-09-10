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


pred_c = []
pred_o = []


# ============================================================
# WALK-FORWARD RIDGE 100
# ============================================================

for i, r in enumerate(rows):

    if i < 3:

        pc = r["base_casa"]
        po = r["base_ospite"]

    else:

        storico = rows[:i]

        X = [[x["volume"]] for x in storico]

        y_c = [
            x["gol_casa"] - x["base_casa"]
            for x in storico
        ]

        y_o = [
            x["gol_ospite"] - x["base_ospite"]
            for x in storico
        ]

        model_c = Ridge(alpha=100.0)
        model_o = Ridge(alpha=100.0)

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


# ============================================================
# FUNZIONI METRICHE
# ============================================================

def calcola(indici, nome):

    yc = [rows[i]["gol_casa"] for i in indici]
    yo = [rows[i]["gol_ospite"] for i in indici]

    bc = [rows[i]["base_casa"] for i in indici]
    bo = [rows[i]["base_ospite"] for i in indici]

    pc = [pred_c[i] for i in indici]
    po = [pred_o[i] for i in indici]

    mae_base = (
        mean_absolute_error(yc, bc)
        + mean_absolute_error(yo, bo)
    ) / 2

    rmse_base = (
        math.sqrt(mean_squared_error(yc, bc))
        + math.sqrt(mean_squared_error(yo, bo))
    ) / 2

    mae_model = (
        mean_absolute_error(yc, pc)
        + mean_absolute_error(yo, po)
    ) / 2

    rmse_model = (
        math.sqrt(mean_squared_error(yc, pc))
        + math.sqrt(mean_squared_error(yo, po))
    ) / 2

    return (
        nome,
        mae_base,
        rmse_base,
        mae_model,
        rmse_model,
        mae_model - mae_base,
        rmse_model - rmse_base,
    )


periodi = [
    (list(range(0, 6)), "Prime 6"),
    (list(range(6, 13)), "Centrale 7"),
    (list(range(13, 20)), "Ultime 7"),
    (list(range(20)), "Totale 20"),
]


print()
print("=" * 100)
print("STABILITA TEMPORALE - RIDGE 100")
print("=" * 100)

print(
    f"{'Periodo':15s}"
    f"{'Base MAE':12s}"
    f"{'R100 MAE':12s}"
    f"{'dMAE':12s}"
    f"{'Base RMSE':12s}"
    f"{'R100 RMSE':12s}"
    f"{'dRMSE':12s}"
)

print("-" * 100)


for indici, nome in periodi:

    (
        nome,
        mb,
        rb,
        mm,
        rm,
        dm,
        dr,
    ) = calcola(indici, nome)

    print(
        f"{nome:15s}"
        f"{mb:12.4f}"
        f"{mm:12.4f}"
        f"{dm:+12.4f}"
        f"{rb:12.4f}"
        f"{rm:12.4f}"
        f"{dr:+12.4f}"
    )


# ============================================================
# PARTITA PER PARTITA
# ============================================================

print()
print("=" * 100)
print("CONFRONTO PARTITA PER PARTITA")
print("=" * 100)

migliori = 0
peggiori = 0
uguali = 0

for i, r in enumerate(rows):

    errore_base = (
        abs(r["gol_casa"] - r["base_casa"])
        + abs(r["gol_ospite"] - r["base_ospite"])
    ) / 2

    errore_ridge = (
        abs(r["gol_casa"] - pred_c[i])
        + abs(r["gol_ospite"] - pred_o[i])
    ) / 2

    diff = errore_ridge - errore_base

    if diff < -1e-9:
        migliori += 1
        stato = "MIGLIORE"

    elif diff > 1e-9:
        peggiori += 1
        stato = "PEGGIORE"

    else:
        uguali += 1
        stato = "UGUALE"

    print(
        f"{i+1:02d} "
        f"{r['casa']} - {r['ospite']:22s} "
        f"base={errore_base:.4f} "
        f"ridge100={errore_ridge:.4f} "
        f"diff={diff:+.4f} "
        f"{stato}"
    )


print()
print("=" * 100)
print("CONTEGGIO")
print("=" * 100)

print(f"Migliori : {migliori}")
print(f"Peggiori : {peggiori}")
print(f"Uguali   : {uguali}")

print()
print("Nessuna modifica al modello principale.")
