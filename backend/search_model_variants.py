import csv
import itertools
import math
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = Path("data/serie_a_features.csv")
BASELINE = Path("data/serie_a_backtest_baseline.csv")
ALPHAS = (1.0, 10.0, 25.0, 50.0, 75.0, 100.0, 150.0, 200.0, 300.0, 500.0)


def num(v):
    if v in (None, ""):
        return np.nan
    return float(v)


def mae(a, b):
    return float(np.mean(np.abs(np.asarray(a) - np.asarray(b))))


def rmse(a, b):
    return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))


def load():
    with FEATURES.open(encoding="utf-8") as f:
        features = list(csv.DictReader(f))
    with BASELINE.open(encoding="utf-8") as f:
        baseline = list(csv.DictReader(f))

    fmap = {(r["data"], r["casa"], r["ospite"]): r for r in features}
    rows = []
    for b in baseline:
        f = fmap.get((b["data"], b["casa"], b["ospite"]))
        if not f:
            continue
        row = dict(b)
        for k, v in f.items():
            row[k] = v
        rows.append(row)
    rows.sort(key=lambda r: r["data"])
    return rows


def residuals(row):
    return (
        float(row["gol_casa_reali"]) - float(row["gol_casa_attesi"]),
        float(row["gol_ospite_reali"]) - float(row["gol_ospite_attesi"]),
    )


def build_features(r):
    def d(a, b):
        x, y = num(r[a]), num(r[b])
        if np.isnan(x) or np.isnan(y):
            return 0.0
        return x - y

    return {
        "volume_tiri": d("casa_tiri_in_porta_totale_pre", "ospite_tiri_in_porta_totale_pre")
        + d("casa_tiri_fuori_totale_pre", "ospite_tiri_fuori_totale_pre"),
        "tiri_porta": d("casa_tiri_in_porta_totale_pre", "ospite_tiri_in_porta_totale_pre"),
        "possesso": d("casa_possesso_totale_pre", "ospite_possesso_totale_pre"),
        "attacchi": d("casa_attacchi_totale_pre", "ospite_attacchi_totale_pre"),
        "attacchi_pericolosi": d("casa_attacchi_pericolosi_totale_pre", "ospite_attacchi_pericolosi_totale_pre"),
        "corner": d("casa_corner_totale_pre", "ospite_corner_totale_pre"),
        "ammonizioni": d("casa_ammonizioni_totale_pre", "ospite_ammonizioni_totale_pre"),
        "xg_fatti": d("casa_xg_fatti_totale_pre", "ospite_xg_fatti_totale_pre"),
        "xg_subiti": d("casa_xg_subiti_totale_pre", "ospite_xg_subiti_totale_pre"),
    }


def evaluate(rows, features):
    out = []
    for alpha in ALPHAS:
        preds_h, preds_a, real_h, real_a = [], [], [], []
        for i, row in enumerate(rows):
            x = np.array([[features[name][i] for name in features]], dtype=float)
            hist = rows[:i]
            if len(hist) < 3:
                ph, pa = float(row["gol_casa_attesi"]), float(row["gol_ospite_attesi"])
            else:
                X = np.array([[features[name][j] for name in features] for j in range(i)], dtype=float)
                yh = np.array([residuals(rows[j])[0] for j in range(i)])
                ya = np.array([residuals(rows[j])[1] for j in range(i)])
                model_h = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
                model_a = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
                model_h.fit(X, yh)
                model_a.fit(X, ya)
                ph = max(0.0, float(row["gol_casa_attesi"]) + model_h.predict(x)[0])
                pa = max(0.0, float(row["gol_ospite_attesi"]) + model_a.predict(x)[0])
            preds_h.append(ph)
            preds_a.append(pa)
            real_h.append(float(row["gol_casa_reali"]))
            real_a.append(float(row["gol_ospite_reali"]))
        out.append((alpha, mae(preds_h, real_h), mae(preds_a, real_a), rmse(preds_h, real_h), rmse(preds_a, real_a)))
    return out


def main():
    rows = load()
    names = [
        "volume_tiri", "tiri_porta", "possesso", "attacchi",
        "attacchi_pericolosi", "corner", "ammonizioni", "xg_fatti", "xg_subiti"
    ]
    single_results = []
    for name in names:
        for alpha, hm, am, hr, ar in evaluate(rows, {name: [build_features(r)[name] for r in rows}):
            single_results.append((hm + am, hr + ar, name, alpha, hm, am, hr, ar))

    combo_results = []
    for a, b in itertools.combinations(names, 2):
        fs = {a: [build_features(r)[a] for r in rows], b: [build_features(r)[b] for r in rows]}
        for alpha, hm, am, hr, ar in evaluate(rows, fs):
            combo_results.append((hm + am, hr + ar, f"{a}+{b}", alpha, hm, am, hr, ar))

    single_results.sort()
    combo_results.sort()
    print("MODEL SEARCH WALK-FORWARD")
    print("partite:", len(rows))
    print("TOP SINGLE")
    for r in single_results[:10]:
        print(r)
    print("TOP COMBO")
    for r in combo_results[:15]:
        print(r)


if __name__ == "__main__":
    main()
