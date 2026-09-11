import csv
import itertools
import math
from pathlib import Path

from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "data" / "serie_a_features.csv"
BASELINE = ROOT / "data" / "serie_a_backtest_baseline.csv"
COMBINATIONS = ROOT / "data" / "backtest_variabili_combinazioni.csv"
OUT = ROOT / "data" / "audit_overfitting_variabili.csv"

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
HOLDOUT = 5


def f(v):
    if v in (None, ""):
        return None
    return float(v)


def load(path):
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def metric(rows, preds):
    if not rows:
        return float("nan"), float("nan")
    e = []
    sq = []
    for r, (ph, pa) in zip(rows, preds):
        eh = ph - float(r["gol_casa_reali"])
        ea = pa - float(r["gol_ospite_reali"])
        e += [abs(eh), abs(ea)]
        sq += [eh * eh, ea * ea]
    return sum(e) / len(e), math.sqrt(sum(sq) / len(sq))


def build_rows():
    features = load(FEATURES)
    baseline = load(BASELINE)
    idx = {(r["data"], r["casa"], r["ospite"]): r for r in features}
    out = []
    for b in baseline:
        r = idx.get((b["data"], b["casa"], b["ospite"]))
        if not r:
            continue
        item = dict(b)
        item["features"] = {}
        for name, (hc, ac) in VARIABLES.items():
            hv, av = f(r[hc]), f(r[ac])
            item["features"][name] = None if hv is None or av is None else hv - av
        out.append(item)
    return out


def evaluate(rows, combo, alpha, end=None):
    data = rows[:end] if end is not None else rows
    preds = []
    for i, row in enumerate(data):
        bh = float(row["gol_casa_attesi"])
        ba = float(row["gol_ospite_attesi"])
        if i < MIN_TRAIN:
            preds.append((bh, ba))
            continue
        train = data[:i]
        X = [[r["features"][v] for v in combo] for r in train]
        yh = [float(r["gol_casa_reali"]) - float(r["gol_casa_attesi"]) for r in train]
        ya = [float(r["gol_ospite_reali"]) - float(r["gol_ospite_attesi"]) for r in train]
        scaler = StandardScaler().fit(X)
        model_h = Ridge(alpha=alpha).fit(scaler.transform(X), yh)
        model_a = Ridge(alpha=alpha).fit(scaler.transform(X), ya)
        xt = scaler.transform([[row["features"][v] for v in combo]])
        preds.append((max(0.0, bh + float(model_h.predict(xt)[0])), max(0.0, ba + float(model_a.predict(xt)[0]))))
    return data, preds


def candidate_key(combo):
    return "+".join(combo)


rows = build_rows()
combo_results = load(COMBINATIONS) if COMBINATIONS.exists() else []
all_candidates = []
for size in range(1, MAX_COMBO + 1):
    for combo in itertools.combinations(VARIABLES, size):
        all_candidates += [(combo, alpha) for alpha in ALPHAS]

results = []
for combo, alpha in all_candidates:
    usable = [r for r in rows if all(r["features"][v] is not None for v in combo)]
    if len(usable) < MIN_TRAIN + 3:
        continue
    full, pred = evaluate(usable, combo, alpha)
    base_pred = [(float(r["gol_casa_attesi"]), float(r["gol_ospite_attesi"])) for r in full]
    mae, rmse = metric(full, pred)
    bmae, brmse = metric(full, base_pred)
    n = len(full)
    third = max(1, n // 3)
    segs = []
    for start, end in ((0, third), (third, min(2 * third, n)), (min(2 * third, n), n)):
        if end - start >= 2:
            sm, sr = metric(full[start:end], pred[start:end])
            sbm, sbr = metric(full[start:end], base_pred[start:end])
            segs.append((sm - sbm, sr - sbr))
    hold = min(HOLDOUT, max(1, n // 4))
    split = n - hold
    train_part = full[:split]
    test_part = full[split:]
    if len(train_part) >= MIN_TRAIN:
        _, train_pred = evaluate(full, combo, alpha, end=split)
        train_mae, train_rmse = metric(train_part, train_pred)
        test_preds = []
        for i, row in enumerate(test_part, start=split):
            bh = float(row["gol_casa_attesi"])
            ba = float(row["gol_ospite_attesi"])
            hist = full[:i]
            X = [[r["features"][v] for v in combo] for r in hist]
            yh = [float(r["gol_casa_reali"]) - float(r["gol_casa_attesi"]) for r in hist]
            ya = [float(r["gol_ospite_reali"]) - float(r["gol_ospite_attesi"]) for r in hist]
            scaler = StandardScaler().fit(X)
            mh = Ridge(alpha=alpha).fit(scaler.transform(X), yh)
            ma = Ridge(alpha=alpha).fit(scaler.transform(X), ya)
            xt = scaler.transform([[row["features"][v] for v in combo]])
            test_preds.append((max(0.0, bh + float(mh.predict(xt)[0])), max(0.0, ba + float(ma.predict(xt)[0]))))
        test_mae, test_rmse = metric(test_part, test_preds)
        base_test = [(float(r["gol_casa_attesi"]), float(r["gol_ospite_attesi"])) for r in test_part]
        base_test_mae, base_test_rmse = metric(test_part, base_test)
    else:
        train_mae = train_rmse = test_mae = test_rmse = float("nan")
        base_test_mae = base_test_rmse = float("nan")
    results.append({
        "combo": candidate_key(combo), "alpha": alpha, "n": n,
        "mae": mae, "rmse": rmse, "delta_mae": mae - bmae, "delta_rmse": rmse - brmse,
        "seg1_dmae": segs[0][0] if len(segs)>0 else float("nan"),
        "seg2_dmae": segs[1][0] if len(segs)>1 else float("nan"),
        "seg3_dmae": segs[2][0] if len(segs)>2 else float("nan"),
        "seg1_drmse": segs[0][1] if len(segs)>0 else float("nan"),
        "seg2_drmse": segs[1][1] if len(segs)>1 else float("nan"),
        "seg3_drmse": segs[2][1] if len(segs)>2 else float("nan"),
        "train_mae": train_mae, "train_rmse": train_rmse,
        "holdout_mae": test_mae, "holdout_rmse": test_rmse,
        "holdout_delta_mae": test_mae - base_test_mae,
        "holdout_delta_rmse": test_rmse - base_test_rmse,
    })

results.sort(key=lambda r: (r["holdout_delta_rmse"], r["holdout_delta_mae"], r["mae"]))

with OUT.open("w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=results[0].keys())
    writer.writeheader(); writer.writerows(results)

print("=" * 110)
print("AUDIT STABILITA TEMPORALE + HOLDOUT + RISCHIO OVERFITTING")
print("=" * 110)
print(f"Partite disponibili: {len(rows)} | Candidati testati: {len(results)} | Holdout: ultimi {HOLDOUT} quando possibile")
print("Top candidati ordinati per miglioramento RMSE HOLDOUT:")
for r in results[:25]:
    stable = sum(x <= 0 for x in (r['seg1_drmse'], r['seg2_drmse'], r['seg3_drmse']) if not math.isnan(x))
    print(f"{r['combo']:<60} a={r['alpha']:<3} n={r['n']:<2} full={r['delta_mae']:+.4f}/{r['delta_rmse']:+.4f} hold={r['holdout_delta_mae']:+.4f}/{r['holdout_delta_rmse']:+.4f} stableRMSE={stable}/3")
print("Nota: il risultato finale non verra' scelto dal miglior punteggio full-sample; verra' privilegiato un candidato che regge holdout e segmenti temporali.")
