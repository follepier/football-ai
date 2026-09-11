import csv
import itertools
import math
from pathlib import Path

from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "data" / "serie_a_features.csv"
BASELINE = ROOT / "data" / "serie_a_backtest_baseline.csv"
OUT = ROOT / "data" / "backtest_variabili_combinazioni.csv"

VARIABLES = {
    "gol": ("casa_gol_fatti_totale_pre", "ospite_gol_fatti_totale_pre"),
    "difesa": ("casa_gol_subiti_totale_pre", "ospite_gol_subiti_totale_pre"),
    "xg": ("casa_xg_fatti_totale_pre", "ospite_xg_fatti_totale_pre"),
    "xg_difesa": ("casa_xg_subiti_totale_pre", "ospite_xg_subiti_totale_pre"),
    "corner": ("casa_corner_totale_pre", "ospite_corner_totale_pre"),
    "ammonizioni": ("casa_ammonizioni_totale_pre", "ospite_ammonizioni_totale_pre"),
    "possesso": ("casa_possesso_totale_pre", "ospite_possesso_totale_pre"),
    "tiri_in_porta": ("casa_tiri_in_porta_totale_pre", "ospite_tiri_in_porta_totale_pre"),
    "tiri_fuori": ("casa_tiri_fuori_totale_pre", "ospite_tiri_fuori_totale_pre"),
    "attacchi": ("casa_attacchi_totale_pre", "ospite_attacchi_totale_pre"),
    "attacchi_pericolosi": ("casa_attacchi_pericolosi_totale_pre", "ospite_attacchi_pericolosi_totale_pre"),
}

ALPHAS = (1, 10, 25, 50, 75, 100, 150, 200, 300, 500)
MIN_TRAIN = 5
MAX_COMBO = 3


def f(value):
    if value in ("", None):
        return None
    return float(value)


def load_csv(path):
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


features = load_csv(FEATURES)
baseline = load_csv(BASELINE)
feature_idx = {(r["data"], r["casa"], r["ospite"]): r for r in features}

rows = []
for b in baseline:
    key = (b["data"], b["casa"], b["ospite"])
    r = feature_idx.get(key)
    if not r:
        continue
    item = dict(b)
    item["features"] = {}
    valid = True
    for name, (hc, ac) in VARIABLES.items():
        hv, av = f(r[hc]), f(r[ac])
        if hv is None or av is None:
            valid = False
            break
        item["features"][name] = hv - av
    if valid:
        rows.append(item)


def metrics(rows, predictions):
    home = [float(r["gol_casa_reali"]) for r in rows]
    away = [float(r["gol_ospite_reali"]) for r in rows]
    ph = [p[0] for p in predictions]
    pa = [p[1] for p in predictions]
    abs_home = [abs(a - b) for a, b in zip(home, ph)]
    abs_away = [abs(a - b) for a, b in zip(away, pa)]
    sq = [(a - b) ** 2 for a, b in zip(home, ph)] + [(a - b) ** 2 for a, b in zip(away, pa)]
    return (sum(abs_home + abs_away) / (len(abs_home) + len(abs_away)), math.sqrt(sum(sq) / len(sq)))


def evaluate(combo, alpha):
    predictions = []
    for i, row in enumerate(rows):
        base_h = float(row["gol_casa_attesi"])
        base_a = float(row["gol_ospite_attesi"])
        if i < MIN_TRAIN:
            predictions.append((base_h, base_a))
            continue

        train = rows[:i]
        X = [[r["features"][v] for v in combo] for r in train]
        y_h = [float(r["gol_casa_reali"]) - float(r["gol_casa_attesi"]) for r in train]
        y_a = [float(r["gol_ospite_reali"]) - float(r["gol_ospite_attesi"]) for r in train]
        scaler = StandardScaler().fit(X)
        Xs = scaler.transform(X)
        Xt = scaler.transform([[row["features"][v] for v in combo]])
        mh = Ridge(alpha=alpha).fit(Xs, y_h)
        ma = Ridge(alpha=alpha).fit(Xs, y_a)
        ph = max(0.0, base_h + float(mh.predict(Xt)[0]))
        pa = max(0.0, base_a + float(ma.predict(Xt)[0]))
        predictions.append((ph, pa))
    mae, rmse = metrics(rows, predictions)
    return mae, rmse


baseline_predictions = [
    (float(r["gol_casa_attesi"]), float(r["gol_ospite_attesi"])) for r in rows
]
base_mae, base_rmse = metrics(rows, baseline_predictions)

results = []
for size in range(1, MAX_COMBO + 1):
    for combo in itertools.combinations(VARIABLES, size):
        for alpha in ALPHAS:
            mae, rmse = evaluate(combo, alpha)
            results.append({
                "combo": "+".join(combo),
                "n": size,
                "alpha": alpha,
                "mae": mae,
                "rmse": rmse,
                "delta_mae": mae - base_mae,
                "delta_rmse": rmse - base_rmse,
            })

results.sort(key=lambda r: (r["mae"], r["rmse"]))

with OUT.open("w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

print("=" * 100)
print("BACKTEST WALK-FORWARD VARIABILI + COMBINAZIONI")
print("=" * 100)
print(f"Partite valide: {len(rows)}")
print(f"Baseline: MAE={base_mae:.4f} RMSE={base_rmse:.4f}")
print("Top 20 candidati:")
for r in results[:20]:
    print(
        f"{r['combo']:<65} alpha={r['alpha']:<3} "
        f"MAE={r['mae']:.4f} RMSE={r['rmse']:.4f} "
        f"dMAE={r['delta_mae']:+.4f} dRMSE={r['delta_rmse']:+.4f}"
    )
