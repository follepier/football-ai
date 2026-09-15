from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

from app.services.analysis import statistiche_contesto, stima_forze
from app.services.football_api import get_understat_league_data


LEAGUES = (
    ("la-liga", "La Liga"),
    ("bundesliga", "Bundesliga"),
    ("ligue-1", "Ligue 1"),
)

STAGIONI_STORICHE = (2023, 2024, 2025)
STAGIONE_HOLDOUT = 2026
EPS = 1e-9
BOOTSTRAP_REPS = 5000
BOOTSTRAP_SEED = 42

# Benchmark congelato e validato sulla Serie A v0.6.0.
SERIE_A_INTERCETTA = 0.214047
SERIE_A_PENDENZA = 0.765037


def finished_matches(competizione, season):
    dati = get_understat_league_data(competizione, season=season)
    partite = [p for p in dati.get("dates", []) if p.get("isResult")]
    partite.sort(key=lambda p: p["datetime"])
    return partite


def build_walkforward_rows(competizione, season):
    """Replica l'engine xG senza usare dati futuri del match corrente."""
    contesto = {
        "casa": defaultdict(list),
        "trasferta": defaultdict(list),
    }
    rows = []

    for partita in finished_matches(competizione, season):
        casa = partita["h"]["title"]
        ospite = partita["a"]["title"]
        xg_casa = float(partita["xG"]["h"])
        xg_ospite = float(partita["xG"]["a"])
        gol_casa = int(partita["goals"]["h"])
        gol_ospite = int(partita["goals"]["a"])

        media_xg_casa = statistiche_contesto(
            contesto["casa"], "fatti"
        )["media"]
        media_xg_trasferta = statistiche_contesto(
            contesto["trasferta"], "fatti"
        )["media"]

        if media_xg_casa > 0 and media_xg_trasferta > 0:
            forza_casa = stima_forze(casa, "casa", contesto)
            forza_ospite = stima_forze(ospite, "trasferta", contesto)

            lambda_casa_raw = (
                media_xg_casa
                * forza_casa["attacco"]
                * forza_ospite["difesa"]
            )
            lambda_ospite_raw = (
                media_xg_trasferta
                * forza_ospite["attacco"]
                * forza_casa["difesa"]
            )

            if (
                math.isfinite(lambda_casa_raw)
                and math.isfinite(lambda_ospite_raw)
                and lambda_casa_raw >= 0
                and lambda_ospite_raw >= 0
            ):
                rows.append({
                    "stagione": season,
                    "data": partita["datetime"],
                    "casa": casa,
                    "ospite": ospite,
                    "gol_casa": gol_casa,
                    "gol_ospite": gol_ospite,
                    "lambda_casa_raw": float(lambda_casa_raw),
                    "lambda_ospite_raw": float(lambda_ospite_raw),
                })

        # Aggiornamento solo dopo la previsione: niente leakage.
        contesto["casa"][casa].append({
            "fatti": xg_casa,
            "subiti": xg_ospite,
        })
        contesto["trasferta"][ospite].append({
            "fatti": xg_ospite,
            "subiti": xg_casa,
        })

    return rows


def flatten_training(rows):
    x = []
    y = []
    for r in rows:
        x.extend([r["lambda_casa_raw"], r["lambda_ospite_raw"]])
        y.extend([r["gol_casa"], r["gol_ospite"]])
    return np.asarray(x, dtype=float), np.asarray(y, dtype=float)


def fit_affine_poisson(rows):
    x, y = flatten_training(rows)

    def objective(theta):
        a, b = theta
        lam = np.maximum(EPS, a + b * x)
        return float(np.mean(lam - y * np.log(lam) + gammaln(y + 1)))

    result = minimize(
        objective,
        x0=np.array([0.15, 0.85], dtype=float),
        method="L-BFGS-B",
        bounds=((0.0, None), (0.0, None)),
    )

    if not result.success:
        raise RuntimeError(f"Ottimizzazione fallita: {result.message}")

    return float(result.x[0]), float(result.x[1])


def apply_affine(rows, a, b, prefix):
    for r in rows:
        r[f"lambda_casa_{prefix}"] = max(
            EPS, a + b * r["lambda_casa_raw"]
        )
        r[f"lambda_ospite_{prefix}"] = max(
            EPS, a + b * r["lambda_ospite_raw"]
        )


def add_raw(rows):
    for r in rows:
        r["lambda_casa_raw_eval"] = max(EPS, r["lambda_casa_raw"])
        r["lambda_ospite_raw_eval"] = max(EPS, r["lambda_ospite_raw"])


def metriche(rows, prefix):
    y = np.asarray(
        [v for r in rows for v in (r["gol_casa"], r["gol_ospite"])],
        dtype=float,
    )
    pred = np.asarray(
        [
            v
            for r in rows
            for v in (
                r[f"lambda_casa_{prefix}"],
                r[f"lambda_ospite_{prefix}"],
            )
        ],
        dtype=float,
    )

    mae = float(np.mean(np.abs(y - pred)))
    rmse = float(np.sqrt(np.mean((y - pred) ** 2)))

    nll_match = []
    for r in rows:
        lh = max(EPS, r[f"lambda_casa_{prefix}"])
        la = max(EPS, r[f"lambda_ospite_{prefix}"])
        gh = r["gol_casa"]
        ga = r["gol_ospite"]
        nll_match.append(
            lh - gh * math.log(lh) + math.lgamma(gh + 1)
            + la - ga * math.log(la) + math.lgamma(ga + 1)
        )

    return {
        "mae": mae,
        "rmse": rmse,
        "nll": float(np.mean(nll_match)),
    }


def bootstrap_delta(rows, base_prefix, candidate_prefix, seed_offset=0):
    rng = np.random.default_rng(BOOTSTRAP_SEED + seed_offset)
    n = len(rows)
    deltas = {"mae": [], "rmse": [], "nll": []}

    for _ in range(BOOTSTRAP_REPS):
        idx = rng.integers(0, n, size=n)
        sample = [rows[i] for i in idx]
        base = metriche(sample, base_prefix)
        candidate = metriche(sample, candidate_prefix)
        for metrica in deltas:
            deltas[metrica].append(base[metrica] - candidate[metrica])

    report = {}
    for metrica, valori in deltas.items():
        arr = np.asarray(valori, dtype=float)
        report[metrica] = {
            "delta": float(np.mean(arr)),
            "lo": float(np.quantile(arr, 0.025)),
            "hi": float(np.quantile(arr, 0.975)),
            "p": float(np.mean(arr > 0)),
        }
    return report


def print_metriche(label, values):
    print(
        f"{label:<24} "
        f"MAE {values['mae']:.6f} | "
        f"RMSE {values['rmse']:.6f} | "
        f"NLL {values['nll']:.6f}"
    )


def print_bootstrap(title, report, candidate_label, base_label):
    print(f"\n{title}")
    print(
        f"Delta positivo = {candidate_label} migliore di {base_label}"
    )
    for metrica in ("mae", "rmse", "nll"):
        r = report[metrica]
        print(
            f"  {metrica.upper():<5} "
            f"delta medio {r['delta']:+.6f} | "
            f"95% CI [{r['lo']:+.6f}, {r['hi']:+.6f}] | "
            f"P(migliora) {r['p']:.3f}"
        )


def audit_league(slug, name, league_index):
    print("\n" + "=" * 78)
    print(f"{name.upper()} · WALK-FORWARD XG AUDIT")
    print("=" * 78)

    per_stagione = {}
    for season in (*STAGIONI_STORICHE, STAGIONE_HOLDOUT):
        rows = build_walkforward_rows(slug, season)
        add_raw(rows)
        apply_affine(
            rows,
            SERIE_A_INTERCETTA,
            SERIE_A_PENDENZA,
            "serie_a",
        )
        per_stagione[season] = rows
        print(f"Stagione {season}: {len(rows)} partite valutabili")

    oos_rows = []
    coeffs = []

    for test_season in (2024, 2025):
        train_rows = [
            r
            for season in STAGIONI_STORICHE
            if season < test_season
            for r in per_stagione[season]
        ]
        a, b = fit_affine_poisson(train_rows)
        apply_affine(
            per_stagione[test_season],
            a,
            b,
            "specifica_oos",
        )
        coeffs.append((test_season, a, b))
        oos_rows.extend(per_stagione[test_season])

    print("\nCOEFFICIENTI SPECIFICI WALK-FORWARD")
    for test_season, a, b in coeffs:
        print(
            f"  Test {test_season}: intercetta={a:.6f}, pendenza={b:.6f}"
        )

    print("\nOOS STORICO 2024+2025")
    print_metriche("RAW", metriche(oos_rows, "raw_eval"))
    print_metriche("Serie A v0.6.0", metriche(oos_rows, "serie_a"))
    print_metriche(f"{name} specifica", metriche(oos_rows, "specifica_oos"))

    print_bootstrap(
        f"BOOTSTRAP {name} SPECIFICA vs RAW · OOS",
        bootstrap_delta(
            oos_rows,
            "raw_eval",
            "specifica_oos",
            seed_offset=league_index * 10 + 1,
        ),
        f"{name} specifica",
        "RAW",
    )
    print_bootstrap(
        f"BOOTSTRAP Serie A v0.6.0 vs RAW · OOS",
        bootstrap_delta(
            oos_rows,
            "raw_eval",
            "serie_a",
            seed_offset=league_index * 10 + 2,
        ),
        "Serie A v0.6.0",
        "RAW",
    )
    print_bootstrap(
        f"BOOTSTRAP {name} SPECIFICA vs SERIE A v0.6.0 · OOS",
        bootstrap_delta(
            oos_rows,
            "serie_a",
            "specifica_oos",
            seed_offset=league_index * 10 + 3,
        ),
        f"{name} specifica",
        "Serie A v0.6.0",
    )

    train_finale = [
        r
        for season in STAGIONI_STORICHE
        for r in per_stagione[season]
    ]
    a_finale, b_finale = fit_affine_poisson(train_finale)
    holdout = per_stagione[STAGIONE_HOLDOUT]
    apply_affine(holdout, a_finale, b_finale, "specifica_finale")

    print("\nCANDIDATO FINALE SPECIFICO · FIT 2023-2025")
    print(f"  intercetta={a_finale:.6f}, pendenza={b_finale:.6f}")

    print(f"\nHOLDOUT {STAGIONE_HOLDOUT} · {len(holdout)} PARTITE")
    print_metriche("RAW", metriche(holdout, "raw_eval"))
    print_metriche("Serie A v0.6.0", metriche(holdout, "serie_a"))
    print_metriche(f"{name} specifica", metriche(holdout, "specifica_finale"))

    if len(holdout) >= 10:
        print_bootstrap(
            f"BOOTSTRAP {name} SPECIFICA vs RAW · HOLDOUT",
            bootstrap_delta(
                holdout,
                "raw_eval",
                "specifica_finale",
                seed_offset=league_index * 10 + 4,
            ),
            f"{name} specifica",
            "RAW",
        )
        print_bootstrap(
            f"BOOTSTRAP Serie A v0.6.0 vs RAW · HOLDOUT",
            bootstrap_delta(
                holdout,
                "raw_eval",
                "serie_a",
                seed_offset=league_index * 10 + 5,
            ),
            "Serie A v0.6.0",
            "RAW",
        )
        print_bootstrap(
            f"BOOTSTRAP {name} SPECIFICA vs SERIE A v0.6.0 · HOLDOUT",
            bootstrap_delta(
                holdout,
                "serie_a",
                "specifica_finale",
                seed_offset=league_index * 10 + 6,
            ),
            f"{name} specifica",
            "Serie A v0.6.0",
        )
    else:
        print("Holdout troppo piccolo per un bootstrap affidabile.")


def main():
    print("===== ALTRI CAMPIONATI · AUDIT CALIBRAZIONE XG =====")
    print("Feature rigorosamente walk-forward; nessun dato futuro nel match.")
    print(f"Bootstrap: {BOOTSTRAP_REPS} repliche")
    print("Nessun coefficiente viene promosso automaticamente.")

    for index, (slug, name) in enumerate(LEAGUES, start=1):
        audit_league(slug, name, index)

    print("\n" + "=" * 78)
    print("AUDIT COMPLETATO")
    print("Confrontare RAW, Serie A v0.6.0 e calibrazione specifica per ogni lega.")
    print("=" * 78)


if __name__ == "__main__":
    main()
