from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

from app.services.analysis import statistiche_contesto, stima_forze
from app.services.football_api import get_understat_league_data


COMPETIZIONE = "premier-league"
STAGIONI_STORICHE = (2023, 2024, 2025)
STAGIONE_HOLDOUT = 2026
EPS = 1e-9
BOOTSTRAP_REPS = 5000
BOOTSTRAP_SEED = 42

# Calibrazione Serie A v0.6.0: viene valutata solo come benchmark esterno.
# Non viene usata per addestrare la calibrazione Premier League.
SERIE_A_INTERCETTA = 0.214047
SERIE_A_PENDENZA = 0.765037

OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "premier_league_xg_backtest.csv"
)


def _finished_matches(season: int):
    dati = get_understat_league_data(COMPETIZIONE, season=season)
    partite = [
        p for p in dati.get("dates", [])
        if p.get("isResult")
    ]
    partite.sort(key=lambda p: p["datetime"])
    return partite


def _build_walkforward_rows(season: int):
    """Replica l'engine xG usando soltanto dati disponibili prima del match."""
    contesto = {
        "casa": defaultdict(list),
        "trasferta": defaultdict(list),
    }
    rows = []

    for partita in _finished_matches(season):
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

        # Il primo match della stagione non ha ancora alcun contesto di lega.
        # Da quel momento in poi, una squadra senza storico usa il fallback
        # neutrale già previsto dall'engine di produzione.
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
                    "xg_reale_casa": xg_casa,
                    "xg_reale_ospite": xg_ospite,
                    "lambda_casa_raw": float(lambda_casa_raw),
                    "lambda_ospite_raw": float(lambda_ospite_raw),
                })

        # Aggiornamento rigorosamente DOPO aver prodotto la previsione.
        contesto["casa"][casa].append({
            "fatti": xg_casa,
            "subiti": xg_ospite,
        })
        contesto["trasferta"][ospite].append({
            "fatti": xg_ospite,
            "subiti": xg_casa,
        })

    return rows


def _flatten_training(rows):
    x = []
    y = []
    for r in rows:
        x.extend([r["lambda_casa_raw"], r["lambda_ospite_raw"]])
        y.extend([r["gol_casa"], r["gol_ospite"]])
    return np.asarray(x, dtype=float), np.asarray(y, dtype=float)


def _fit_affine_poisson(rows):
    """Fit prespecificato: lambda = a + b * lambda_raw, minimizzando Poisson NLL."""
    x, y = _flatten_training(rows)

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


def _apply_affine(rows, a, b, prefix):
    for r in rows:
        r[f"lambda_casa_{prefix}"] = max(
            EPS, a + b * r["lambda_casa_raw"]
        )
        r[f"lambda_ospite_{prefix}"] = max(
            EPS, a + b * r["lambda_ospite_raw"]
        )


def _metriche(rows, prefix):
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
        nll = (
            lh - gh * math.log(lh) + math.lgamma(gh + 1)
            + la - ga * math.log(la) + math.lgamma(ga + 1)
        )
        nll_match.append(nll)

    return {
        "mae": mae,
        "rmse": rmse,
        "nll": float(np.mean(nll_match)),
    }


def _bootstrap_delta(rows, base_prefix, candidate_prefix):
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    n = len(rows)
    deltas = {"mae": [], "rmse": [], "nll": []}

    for _ in range(BOOTSTRAP_REPS):
        idx = rng.integers(0, n, size=n)
        sample = [rows[i] for i in idx]
        base = _metriche(sample, base_prefix)
        candidate = _metriche(sample, candidate_prefix)
        for metrica in deltas:
            # Positivo = candidato migliore del baseline.
            deltas[metrica].append(
                base[metrica] - candidate[metrica]
            )

    report = {}
    for metrica, valori in deltas.items():
        arr = np.asarray(valori, dtype=float)
        report[metrica] = {
            "media_delta": float(np.mean(arr)),
            "ci_2_5": float(np.quantile(arr, 0.025)),
            "ci_97_5": float(np.quantile(arr, 0.975)),
            "prob_migliora": float(np.mean(arr > 0)),
        }
    return report


def _print_metriche(titolo, metriche):
    print(
        f"{titolo:<25} "
        f"MAE {metriche['mae']:.6f} | "
        f"RMSE {metriche['rmse']:.6f} | "
        f"NLL {metriche['nll']:.6f}"
    )


def _print_bootstrap(titolo, report):
    print(f"\n{titolo}")
    print("Delta positivo = calibrazione migliore del RAW")
    for metrica in ("mae", "rmse", "nll"):
        r = report[metrica]
        print(
            f"  {metrica.upper():<5} "
            f"delta medio {r['media_delta']:+.6f} | "
            f"95% CI [{r['ci_2_5']:+.6f}, {r['ci_97_5']:+.6f}] | "
            f"P(migliora) {r['prob_migliora']:.3f}"
        )


def main():
    print("===== PREMIER LEAGUE · WALK-FORWARD XG AUDIT =====")
    print("Nessuna informazione futura viene usata nelle feature del match.")

    per_stagione = {}
    for season in (*STAGIONI_STORICHE, STAGIONE_HOLDOUT):
        rows = _build_walkforward_rows(season)
        per_stagione[season] = rows
        print(f"Stagione {season}: {len(rows)} partite valutabili")

    # RAW e benchmark Serie A su tutte le righe.
    for rows in per_stagione.values():
        for r in rows:
            r["lambda_casa_raw_eval"] = max(EPS, r["lambda_casa_raw"])
            r["lambda_ospite_raw_eval"] = max(EPS, r["lambda_ospite_raw"])
        _apply_affine(
            rows,
            SERIE_A_INTERCETTA,
            SERIE_A_PENDENZA,
            "serie_a",
        )

    # OOS storico: 2024 calibrata esclusivamente su 2023;
    # 2025 calibrata esclusivamente su 2023+2024.
    oos_rows = []
    fold_coeffs = []

    for test_season in (2024, 2025):
        train_seasons = tuple(
            s for s in STAGIONI_STORICHE if s < test_season
        )
        train_rows = [
            r
            for s in train_seasons
            for r in per_stagione[s]
        ]
        test_rows = per_stagione[test_season]
        a, b = _fit_affine_poisson(train_rows)
        _apply_affine(test_rows, a, b, "premier_oos")
        fold_coeffs.append((train_seasons, test_season, a, b))
        oos_rows.extend(test_rows)

    print("\n===== COEFFICIENTI WALK-FORWARD =====")
    for train_seasons, test_season, a, b in fold_coeffs:
        print(
            f"Train {train_seasons} -> Test {test_season}: "
            f"intercetta={a:.6f}, pendenza={b:.6f}"
        )

    print("\n===== OOS STORICO COMBINATO 2024+2025 =====")
    _print_metriche("RAW", _metriche(oos_rows, "raw_eval"))
    _print_metriche("Serie A v0.6.0", _metriche(oos_rows, "serie_a"))
    _print_metriche("Premier OOS", _metriche(oos_rows, "premier_oos"))
    _print_bootstrap(
        "BOOTSTRAP PREMIER OOS vs RAW",
        _bootstrap_delta(oos_rows, "raw_eval", "premier_oos"),
    )

    # Candidate finale Premier: fit solo 2023-2025, poi holdout 2026 intatto.
    train_finale = [
        r
        for s in STAGIONI_STORICHE
        for r in per_stagione[s]
    ]
    a_finale, b_finale = _fit_affine_poisson(train_finale)
    holdout = per_stagione[STAGIONE_HOLDOUT]
    _apply_affine(holdout, a_finale, b_finale, "premier_finale")

    print("\n===== CANDIDATO FINALE (FIT 2023-2025) =====")
    print(
        f"intercetta={a_finale:.6f}, "
        f"pendenza={b_finale:.6f}"
    )

    print(f"\n===== HOLDOUT {STAGIONE_HOLDOUT} =====")
    print(f"Partite holdout: {len(holdout)}")
    _print_metriche("RAW", _metriche(holdout, "raw_eval"))
    _print_metriche("Serie A v0.6.0", _metriche(holdout, "serie_a"))
    _print_metriche("Premier candidata", _metriche(holdout, "premier_finale"))

    if len(holdout) >= 10:
        _print_bootstrap(
            f"BOOTSTRAP HOLDOUT {STAGIONE_HOLDOUT} vs RAW",
            _bootstrap_delta(holdout, "raw_eval", "premier_finale"),
        )
    else:
        print(
            "\nHoldout troppo piccolo per attribuire peso forte al bootstrap "
            "(<10 partite valutabili)."
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    all_rows = [
        r
        for season in (*STAGIONI_STORICHE, STAGIONE_HOLDOUT)
        for r in per_stagione[season]
    ]

    # Uniformiamo le colonne mancanti nei fold non testati.
    fieldnames = [
        "stagione", "data", "casa", "ospite",
        "gol_casa", "gol_ospite",
        "xg_reale_casa", "xg_reale_ospite",
        "lambda_casa_raw", "lambda_ospite_raw",
        "lambda_casa_raw_eval", "lambda_ospite_raw_eval",
        "lambda_casa_serie_a", "lambda_ospite_serie_a",
        "lambda_casa_premier_oos", "lambda_ospite_premier_oos",
        "lambda_casa_premier_finale", "lambda_ospite_premier_finale",
    ]

    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in all_rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    print(f"\nCSV salvato: {OUTPUT}")
    print("\nNOTA: nessun coefficiente viene promosso automaticamente in produzione.")


if __name__ == "__main__":
    main()
