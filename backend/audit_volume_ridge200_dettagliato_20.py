import csv
import math

from sklearn.linear_model import Ridge


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

    f = idx[(b["data"], b["casa"], b["ospite"])]

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
        "gc": float(b["gol_casa_reali"]),
        "go": float(b["gol_ospite_reali"]),
        "bc": float(b["gol_casa_attesi"]),
        "bo": float(b["gol_ospite_attesi"]),
        "volume": volume,
    })


pred_c = []
pred_o = []


for i, r in enumerate(rows):

    if i < 3:

        pc = r["bc"]
        po = r["bo"]

    else:

        storico = rows[:i]

        X = [[x["volume"]] for x in storico]

        yc = [
            x["gc"] - x["bc"]
            for x in storico
        ]

        yo = [
            x["go"] - x["bo"]
            for x in storico
        ]

        mc = Ridge(alpha=200.0)
        mo = Ridge(alpha=200.0)

        mc.fit(X, yc)
        mo.fit(X, yo)

        corr_c = mc.predict([[r["volume"]]])[0]
        corr_o = mo.predict([[r["volume"]]])[0]

        pc = max(0.0, r["bc"] + corr_c)
        po = max(0.0, r["bo"] + corr_o)

    pred_c.append(pc)
    pred_o.append(po)


print()
print("=" * 115)
print("AUDIT DETTAGLIATO - BASELINE vs RIDGE 200 + VOLUME")
print("=" * 115)

print(
    f"{'#':3s}"
    f"{'Partita':28s}"
    f"{'Vol':8s}"
    f"{'Reale':10s}"
    f"{'Base':14s}"
    f"{'Ridge200':14s}"
    f"{'Errore B':12s}"
    f"{'Errore R':12s}"
    f"{'Delta':10s}"
)

print("-" * 115)


migliori = 0
peggiori = 0
uguali = 0


for i, r in enumerate(rows):

    errore_base = (
        abs(r["gc"] - r["bc"])
        + abs(r["go"] - r["bo"])
    ) / 2

    errore_ridge = (
        abs(r["gc"] - pred_c[i])
        + abs(r["go"] - pred_o[i])
    ) / 2

    delta = errore_ridge - errore_base

    if delta < -1e-9:
        migliori += 1
        stato = "M"
    elif delta > 1e-9:
        peggiori += 1
        stato = "P"
    else:
        uguali += 1
        stato = "="

    print(
        f"{i+1:02d} "
        f"{r['casa']} - {r['ospite']:22s} "
        f"{r['volume']:+7.2f} "
        f"{r['gc']:.0f}-{r['go']:.0f}      "
        f"{r['bc']:.3f}-{r['bo']:.3f}      "
        f"{pred_c[i]:.3f}-{pred_o[i]:.3f}      "
        f"{errore_base:.4f}      "
        f"{errore_ridge:.4f}      "
        f"{delta:+.4f} {stato}"
    )


print()
print("=" * 115)
print("CONTEGGIO")
print("=" * 115)

print(f"Migliori : {migliori}")
print(f"Peggiori : {peggiori}")
print(f"Uguali   : {uguali}")


# ============================================================
# ERRORI CASA / TRASFERTA
# ============================================================

base_home = [
    abs(r["gc"] - r["bc"])
    for r in rows
]

ridge_home = [
    abs(r["gc"] - pred_c[i])
    for i, r in enumerate(rows)
]

base_away = [
    abs(r["go"] - r["bo"])
    for r in rows
]

ridge_away = [
    abs(r["go"] - pred_o[i])
    for i, r in enumerate(rows)
]


def media(v):
    return sum(v) / len(v)


print()
print("=" * 115)
print("ERRORE SEPARATO CASA / TRASFERTA")
print("=" * 115)

print(
    f"Casa      | "
    f"Baseline MAE={media(base_home):.4f} | "
    f"Ridge200 MAE={media(ridge_home):.4f} | "
    f"Delta={media(ridge_home)-media(base_home):+.4f}"
)

print(
    f"Trasferta | "
    f"Baseline MAE={media(base_away):.4f} | "
    f"Ridge200 MAE={media(ridge_away):.4f} | "
    f"Delta={media(ridge_away)-media(base_away):+.4f}"
)


print()
print("=" * 115)
print("CORREZIONI RIDGE 200")
print("=" * 115)

for i, r in enumerate(rows):

    corr_c = pred_c[i] - r["bc"]
    corr_o = pred_o[i] - r["bo"]

    print(
        f"{i+1:02d} "
        f"{r['casa']} - {r['ospite']:22s} | "
        f"correzione casa={corr_c:+.4f} | "
        f"correzione ospite={corr_o:+.4f}"
    )


print()
print("Nessuna modifica al modello principale.")
