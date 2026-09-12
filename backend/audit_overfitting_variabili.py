import csv
import itertools
import math
from pathlib import Path

from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "data" / "serie_a_features.csv"
BASELINE = ROOT / "data" / "serie_a_backtest_baseline.csv"
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
ALPHAS = (0.1, 1, 10, 25, 50, 75, 100, 150, 200, 300, 500)
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


def metrics(rows, preds):
    if not rows:
        return float("nan"), float("nan"), float("nan"), float("nan")
    eh = [ph - float(r["gol_casa_reali"]) for r, (ph, pa) in zip(rows, preds)]
    ea = [pa - float(r["gol_ospite_reali"]) for r, (ph, pa) in zip(rows, preds)]
    mae_h = sum(abs(x) for x in eh) / len(eh)
    mae_a = sum(abs(x) for x in ea) / len(ea)
    rmse_h = math.sqrt(sum(x * x for x in eh) / len(eh))
    rmse_a = math.sqrt(sum(x * x for x in ea) / len(ea))
    # Identico al benchmark ufficiale: media semplice casa/ospite.
    return (mae_h + mae_a) / 2, (rmse_h + rmse_a) / 2, mae_h, mae_a


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


def rolling_predict(rows, combo, alpha, start=MIN_TRAIN, end=None):
    end = len(rows) if end is None else end
    preds = []
    for i in range(start, end):
        row = rows[i]
        hist = rows[:i]
        X = [[r["features"][v] for v in combo] for r in hist]
        yh = [float(r["gol_casa_reali"]) - float(r["gol_casa_attesi"]) for r in hist]
        ya = [float(r["gol_ospite_reali"]) - float(r["gol_ospite_attesi"]) for r in hist]
        scaler = StandardScaler().fit(X)
        mh = Ridge(alpha=alpha).fit(scaler.transform(X), yh)
        ma = Ridge(alpha=alpha).fit(scaler.transform(X), ya)
        xt = scaler.transform([[row["features"][v] for v in combo]])
        bh = float(row["gol_casa_attesi"])
        ba = float(row["gol_ospite_attesi"])
        preds.append((max(0.0, bh + float(mh.predict(xt)[0])), max(0.0, ba + float(ma.predict(xt)[0]))))
    return preds


rows = build_rows()
results = []

for size in range(1, MAX_COMBO + 1):
    for combo in itertools.combinations(VARIABLES, size):
        usable = [r for r in rows if all(r["features"][v] is not None for v in combo)]
        n = len(usable)
        if n < MIN_TRAIN + 3:
            continue

        base_all = [(float(r["gol_casa_attesi"]), float(r["gol_ospite_attesi"])) for r in usable]
        base_mae, base_rmse, _, _ = metrics(usable, base_all)
        hold = min(HOLDOUT, max(1, n // 4))
        split = n - hold

        for alpha in ALPHAS:
            pred_all = rolling_predict(usable, combo, alpha)
            eval_rows = usable[MIN_TRAIN:]
            model_mae, model_rmse, _, _ = metrics(eval_rows, pred_all)
            base_eval = base_all[MIN_TRAIN:]
            eval_base_mae, eval_base_rmse, _, _ = metrics(eval_rows, base_eval)

            # Tre segmenti temporali sulle stesse previsioni walk-forward.
            m = len(eval_rows)
            third = max(1, m // 3)
            seg_drmse = []
            seg_dmae = []
            for s, e in ((0, third), (third, min(2 * third, m)), (min(2 * third, m), m)):
                if e - s >= 2:
                    sm, sr, _, _ = metrics(eval_rows[s:e], pred_all[s:e])
                    bm, br, _, _ = metrics(eval_rows[s:e], base_eval[s:e])
                    seg_dmae.append(sm - bm)
                    seg_drmse.append(sr - br)

            # Holdout: il modello continua ad allenarsi solo sulle partite precedenti.
            hold_rows = usable[split:]
            hold_preds = rolling_predict(usable, combo, alpha, start=split, end=n)
            hold_base = base_all[split:]
            hold_mae, hold_rmse, _, _ = metrics(hold_rows, hold_preds)
            hold_base_mae, hold_base_rmse, _, _ = metrics(hold_rows, hold_base)

            # Proxy conservativo del rischio: gap assoluto tra miglioramento eval e holdout.
            generalization_gap_mae = abs((model_mae - eval_base_mae) - (hold_mae - hold_base_mae))
            generalization_gap_rmse = abs((model_rmse - eval_base_rmse) - (hold_rmse - hold_base_rmse))
            stable_rmse = sum(x <= 0 for x in seg_drmse)
            stable_mae = sum(x <= 0 for x in seg_dmae)

            results.append({
                "combo": "+".join(combo),
                "alpha": alpha,
                "n": n,
                "eval_n": len(eval_rows),
                "mae": model_mae,
                "rmse": model_rmse,
                "delta_mae": model_mae - eval_base_mae,
                "delta_rmse": model_rmse - eval_base_rmse,
                "seg1_dmae": seg_dmae[0] if len(seg_dmae) > 0 else float("nan"),
                "seg2_dmae": seg_dmae[1] if len(seg_dmae) > 1 else float("nan"),
                "seg3_dmae": seg_dmae[2] if len(seg_dmae) > 2 else float("nan"),
                "seg1_drmse": seg_drmse[0] if len(seg_drmse) > 0 else float("nan"),
                "seg2_drmse": seg_drmse[1] if len(seg_drmse) > 1 else float("nan"),
                "seg3_drmse": seg_drmse[2] if len(seg_drmse) > 2 else float("nan"),
                "stable_mae": stable_mae,
                "stable_rmse": stable_rmse,
                "holdout_mae": hold_mae,
                "holdout_rmse": hold_rmse,
                "holdout_delta_mae": hold_mae - hold_base_mae,
                "holdout_delta_rmse": hold_rmse - hold_base_rmse,
                "generalization_gap_mae": generalization_gap_mae,
                "generalization_gap_rmse": generalization_gap_rmse,
            })

# Prima robustezza holdout, poi stabilita', poi RMSE/MAE globale.
results.sort(key=lambda r: (
    r["holdout_delta_rmse"],
    r["holdout_delta_mae"],
    -r["stable_rmse"],
    r["generalization_gap_rmse"],
    r["rmse"],
    r["mae"],
))

with OUT.open("w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

print("=" * 120)
print("AUDIT CORRETTO: MAE + RMSE + STABILITA TEMPORALE + HOLDOUT + OVERFITTING")
print("=" * 120)
print(f"Partite: {len(rows)} | Candidati: {len(results)} | Holdout: ultime {HOLDOUT} quando possibile")
print("RMSE coerente con il benchmark ufficiale: media RMSE casa/ospite.")
print("Top 25 ordinati prima per RMSE holdout, poi MAE holdout e stabilita':")
for r in results[:25]:
    print(
        f"{r['combo']:<58} a={r['alpha']:<5} n={r['n']:<2} "
        f"full={r['delta_mae']:+.4f}/{r['delta_rmse']:+.4f} "
        f"hold={r['holdout_delta_mae']:+.4f}/{r['holdout_delta_rmse']:+.4f} "
        f"stable={r['stable_rmse']}/3 gap={r['generalization_gap_rmse']:.4f}"
    )
print("Nessuna integrazione automatica nel modello principale: la selezione finale richiede robustezza, non solo il miglior punteggio.")
