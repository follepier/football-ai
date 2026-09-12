import csv
import math
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

FEATURES = "data/serie_a_features.csv"
BASELINE = "data/serie_a_backtest_baseline.csv"

with open(FEATURES, encoding="utf-8") as f:
    features = list(csv.DictReader(f))
with open(BASELINE, encoding="utf-8") as f:
    baseline = list(csv.DictReader(f))

idx = {(r["data"], r["casa"], r["ospite"]): r for r in features}

# Only pre-match variables. Same-match outcome/statistics are never used.
feature_names = [
    "casa_gol_fatti_totale_pre", "casa_gol_fatti_contesto_pre",
    "ospite_gol_fatti_totale_pre", "ospite_gol_fatti_contesto_pre",
    "casa_gol_subiti_totale_pre", "casa_gol_subiti_contesto_pre",
    "ospite_gol_subiti_totale_pre", "ospite_gol_subiti_contesto_pre",
    "casa_xg_fatti_totale_pre", "casa_xg_fatti_contesto_pre",
    "ospite_xg_fatti_totale_pre", "ospite_xg_fatti_contesto_pre",
    "casa_xg_subiti_totale_pre", "casa_xg_subiti_contesto_pre",
    "ospite_xg_subiti_totale_pre", "ospite_xg_subiti_contesto_pre",
    "casa_corner_totale_pre", "casa_corner_contesto_pre",
    "ospite_corner_totale_pre", "ospite_corner_contesto_pre",
    "casa_ammonizioni_totale_pre", "casa_ammonizioni_contesto_pre",
    "ospite_ammonizioni_totale_pre", "ospite_ammonizioni_contesto_pre",
    "casa_possesso_totale_pre", "casa_possesso_contesto_pre",
    "ospite_possesso_totale_pre", "ospite_possesso_contesto_pre",
    "casa_tiri_in_porta_totale_pre", "casa_tiri_in_porta_contesto_pre",
    "ospite_tiri_in_porta_totale_pre", "ospite_tiri_in_porta_contesto_pre",
    "casa_tiri_fuori_totale_pre", "casa_tiri_fuori_contesto_pre",
    "ospite_tiri_fuori_totale_pre", "ospite_tiri_fuori_contesto_pre",
    "casa_attacchi_totale_pre", "casa_attacchi_contesto_pre",
    "ospite_attacchi_totale_pre", "ospite_attacchi_contesto_pre",
    "casa_attacchi_pericolosi_totale_pre", "casa_attacchi_pericolosi_contesto_pre",
    "ospite_attacchi_pericolosi_totale_pre", "ospite_attacchi_pericolosi_contesto_pre",
]


def n(x):
    return float(x) if x not in ("", None) else 0.0

rows = []
for b in baseline:
    f = idx[(b["data"], b["casa"], b["ospite"])]
    rows.append({
        "gc": float(b["gol_casa_reali"]),
        "go": float(b["gol_ospite_reali"]),
        "bc": float(b["gol_casa_attesi"]),
        "bo": float(b["gol_ospite_attesi"]),
        "X": [n(f[k]) for k in feature_names],
        "match": f'{b["casa"]} - {b["ospite"]}',
    })

for alpha in (10.0, 50.0, 100.0, 200.0, 500.0, 1000.0):
    pc, po = [], []
    for i, r in enumerate(rows):
        if i < 8:
            pc.append(r["bc"]); po.append(r["bo"])
            continue
        hist = rows[:i]
        X = [x["X"] for x in hist]
        yc = [x["gc"] - x["bc"] for x in hist]
        yo = [x["go"] - x["bo"] for x in hist]
        mc = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        mo = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        mc.fit(X, yc); mo.fit(X, yo)
        pc.append(max(0.0, r["bc"] + mc.predict([r["X"]])[0]))
        po.append(max(0.0, r["bo"] + mo.predict([r["X"]])[0]))

    def mae(pred_c, pred_o, inds):
        return sum((abs(rows[i]["gc"]-pred_c[i]) + abs(rows[i]["go"]-pred_o[i]))/2 for i in inds)/len(inds)
    def rmse(pred_c, pred_o, inds):
        a = math.sqrt(sum((rows[i]["gc"]-pred_c[i])**2 for i in inds)/len(inds))
        b = math.sqrt(sum((rows[i]["go"]-pred_o[i])**2 for i in inds)/len(inds))
        return (a+b)/2

    inds = list(range(8, len(rows)))
    base_mae = mae([r["bc"] for r in rows], [r["bo"] for r in rows], inds)
    base_rmse = rmse([r["bc"] for r in rows], [r["bo"] for r in rows], inds)
    print(f"alpha={alpha:7.1f} | baseline MAE={base_mae:.4f} RMSE={base_rmse:.4f} | Ridge MAE={mae(pc,po,inds):.4f} RMSE={rmse(pc,po,inds):.4f} | dMAE={mae(pc,po,inds)-base_mae:+.4f} dRMSE={rmse(pc,po,inds)-base_rmse:+.4f}")
