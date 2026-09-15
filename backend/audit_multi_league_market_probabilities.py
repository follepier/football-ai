from __future__ import annotations

import math

import numpy as np

from backtest_other_leagues_xg_calibration import (
    STAGIONE_HOLDOUT,
    build_walkforward_rows,
)


LEAGUES = (
    ("premier-league", "Premier League"),
    ("la-liga", "La Liga"),
    ("bundesliga", "Bundesliga"),
    ("ligue-1", "Ligue 1"),
)

INTERCETTA = 0.214047
PENDENZA = 0.765037
BOOTSTRAP_REPS = 5000
BOOTSTRAP_SEED = 42
EPS = 1e-12
MAX_GOALS = 20


def poisson_pmf(lam, k):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def market_probs(lh, la):
    grid = []
    for gh in range(MAX_GOALS + 1):
        ph = poisson_pmf(lh, gh)
        for ga in range(MAX_GOALS + 1):
            p = ph * poisson_pmf(la, ga)
            grid.append((gh, ga, p))

    total = sum(p for _, _, p in grid)
    if total <= 0:
        raise RuntimeError("Massa di probabilita nulla")

    grid = [(gh, ga, p / total) for gh, ga, p in grid]

    p1 = sum(p for gh, ga, p in grid if gh > ga)
    px = sum(p for gh, ga, p in grid if gh == ga)
    p2 = sum(p for gh, ga, p in grid if gh < ga)

    return {
        "1x2": (p1, px, p2),
        "over_1_5": sum(p for gh, ga, p in grid if gh + ga > 1),
        "over_2_5": sum(p for gh, ga, p in grid if gh + ga > 2),
        "over_3_5": sum(p for gh, ga, p in grid if gh + ga > 3),
        "btts": sum(p for gh, ga, p in grid if gh > 0 and ga > 0),
    }


def binary_logloss(y, p):
    p = min(max(float(p), EPS), 1.0 - EPS)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def binary_brier(y, p):
    return (float(p) - float(y)) ** 2


def multiclass_logloss(y_idx, probs):
    return -math.log(max(float(probs[y_idx]), EPS))


def multiclass_brier(y_idx, probs):
    return sum(
        (float(p) - (1.0 if i == y_idx else 0.0)) ** 2
        for i, p in enumerate(probs)
    )


def enrich_rows(slug):
    rows = build_walkforward_rows(slug, STAGIONE_HOLDOUT)
    out = []

    for r in rows:
        raw_h = max(EPS, float(r["lambda_casa_raw"]))
        raw_a = max(EPS, float(r["lambda_ospite_raw"]))
        cal_h = max(EPS, INTERCETTA + PENDENZA * raw_h)
        cal_a = max(EPS, INTERCETTA + PENDENZA * raw_a)

        gh = int(r["gol_casa"])
        ga = int(r["gol_ospite"])
        result_idx = 0 if gh > ga else (1 if gh == ga else 2)

        raw = market_probs(raw_h, raw_a)
        cal = market_probs(cal_h, cal_a)

        outcomes = {
            "over_1_5": int(gh + ga > 1),
            "over_2_5": int(gh + ga > 2),
            "over_3_5": int(gh + ga > 3),
            "btts": int(gh > 0 and ga > 0),
        }

        losses = {
            "1x2_logloss_raw": multiclass_logloss(result_idx, raw["1x2"]),
            "1x2_logloss_cal": multiclass_logloss(result_idx, cal["1x2"]),
            "1x2_brier_raw": multiclass_brier(result_idx, raw["1x2"]),
            "1x2_brier_cal": multiclass_brier(result_idx, cal["1x2"]),
        }

        for market, y in outcomes.items():
            losses[f"{market}_logloss_raw"] = binary_logloss(y, raw[market])
            losses[f"{market}_logloss_cal"] = binary_logloss(y, cal[market])
            losses[f"{market}_brier_raw"] = binary_brier(y, raw[market])
            losses[f"{market}_brier_cal"] = binary_brier(y, cal[market])

        out.append(losses)

    return out


def metrics(rows):
    result = {}
    markets = ("1x2", "over_1_5", "over_2_5", "over_3_5", "btts")
    for market in markets:
        for metric in ("logloss", "brier"):
            for version in ("raw", "cal"):
                key = f"{market}_{metric}_{version}"
                result[key] = float(np.mean([r[key] for r in rows]))
    return result


def bootstrap(rows, seed_offset=0):
    rng = np.random.default_rng(BOOTSTRAP_SEED + seed_offset)
    n = len(rows)
    markets = ("1x2", "over_1_5", "over_2_5", "over_3_5", "btts")
    keys = [(m, s) for m in markets for s in ("logloss", "brier")]
    deltas = {k: [] for k in keys}

    for _ in range(BOOTSTRAP_REPS):
        idx = rng.integers(0, n, size=n)
        sample = [rows[i] for i in idx]
        vals = metrics(sample)
        for market, score in keys:
            raw = vals[f"{market}_{score}_raw"]
            cal = vals[f"{market}_{score}_cal"]
            deltas[(market, score)].append(raw - cal)

    report = {}
    for key, values in deltas.items():
        arr = np.asarray(values, dtype=float)
        report[key] = {
            "delta": float(np.mean(arr)),
            "lo": float(np.quantile(arr, 0.025)),
            "hi": float(np.quantile(arr, 0.975)),
            "p": float(np.mean(arr > 0)),
        }
    return report


def print_report(name, rows, seed_offset):
    vals = metrics(rows)
    boot = bootstrap(rows, seed_offset=seed_offset)

    print("\n" + "=" * 84)
    print(f"{name.upper()} · HOLDOUT {STAGIONE_HOLDOUT} · {len(rows)} PARTITE")
    print("=" * 84)
    print("Delta positivo = calibrazione v0.6.0 migliore del RAW")

    labels = {
        "1x2": "1X2",
        "over_1_5": "O/U 1.5",
        "over_2_5": "O/U 2.5",
        "over_3_5": "O/U 3.5",
        "btts": "Gol/No Gol",
    }

    for market in ("1x2", "over_1_5", "over_2_5", "over_3_5", "btts"):
        print(f"\n{labels[market]}")
        for score in ("logloss", "brier"):
            raw = vals[f"{market}_{score}_raw"]
            cal = vals[f"{market}_{score}_cal"]
            b = boot[(market, score)]
            print(
                f"  {score.upper():<7} RAW {raw:.6f} | CAL {cal:.6f} | "
                f"delta {b['delta']:+.6f} | "
                f"95% CI [{b['lo']:+.6f}, {b['hi']:+.6f}] | "
                f"P {b['p']:.3f}"
            )


def main():
    print("===== MULTI-LEAGUE · VALIDAZIONE PROBABILITA MERCATI =====")
    print("Nuovi campionati: Premier League, La Liga, Bundesliga, Ligue 1")
    print("Holdout 2026 soltanto: nessun refit sui dati di test.")
    print(
        f"Calibrazione congelata: lambda = {INTERCETTA:.6f} + "
        f"{PENDENZA:.6f} * lambda_raw"
    )
    print(f"Bootstrap: {BOOTSTRAP_REPS} repliche")

    combined = []
    for i, (slug, name) in enumerate(LEAGUES, start=1):
        rows = enrich_rows(slug)
        combined.extend(rows)
        print_report(name, rows, seed_offset=i * 100)

    print_report("NUOVI 4 CAMPIONATI COMBINATI", combined, seed_offset=999)

    print("\n===== NOTA =====")
    print("Nessuna modifica automatica al modello di produzione.")
    print("La promozione richiede coerenza tra xG e mercati probabilistici.")


if __name__ == "__main__":
    main()
