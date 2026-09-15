from __future__ import annotations

from backtest_premier_xg_calibration import (
    BOOTSTRAP_REPS,
    BOOTSTRAP_SEED,
    COMPETIZIONE,
    EPS,
    SERIE_A_INTERCETTA,
    SERIE_A_PENDENZA,
    STAGIONI_STORICHE,
    STAGIONE_HOLDOUT,
    _apply_affine,
    _bootstrap_delta,
    _build_walkforward_rows,
    _fit_affine_poisson,
    _metriche,
    _print_bootstrap,
    _print_metriche,
)


def main():
    print("===== PREMIER LEAGUE · CONFRONTO CALIBRAZIONI =====")
    print(f"Competizione: {COMPETIZIONE}")
    print(f"Bootstrap reps: {BOOTSTRAP_REPS} | seed: {BOOTSTRAP_SEED}")

    per_stagione = {
        season: _build_walkforward_rows(season)
        for season in (*STAGIONI_STORICHE, STAGIONE_HOLDOUT)
    }

    # Serie A v0.6.0: benchmark fisso, mai rifittato sui dati Premier.
    for rows in per_stagione.values():
        _apply_affine(
            rows,
            SERIE_A_INTERCETTA,
            SERIE_A_PENDENZA,
            "serie_a",
        )

    # Premier walk-forward OOS storico.
    oos_rows = []
    for test_season in (2024, 2025):
        train_rows = [
            r
            for season in STAGIONI_STORICHE
            if season < test_season
            for r in per_stagione[season]
        ]
        a, b = _fit_affine_poisson(train_rows)
        _apply_affine(
            per_stagione[test_season],
            a,
            b,
            "premier_oos",
        )
        oos_rows.extend(per_stagione[test_season])

    print("\n===== OOS STORICO 2024+2025 =====")
    _print_metriche("Serie A v0.6.0", _metriche(oos_rows, "serie_a"))
    _print_metriche("Premier OOS", _metriche(oos_rows, "premier_oos"))
    _print_bootstrap(
        "BOOTSTRAP PREMIER OOS vs SERIE A v0.6.0",
        _bootstrap_delta(oos_rows, "serie_a", "premier_oos"),
    )

    # Premier candidata finale: fit 2023-2025, test 2026.
    train_finale = [
        r
        for season in STAGIONI_STORICHE
        for r in per_stagione[season]
    ]
    a_finale, b_finale = _fit_affine_poisson(train_finale)
    holdout = per_stagione[STAGIONE_HOLDOUT]
    _apply_affine(
        holdout,
        a_finale,
        b_finale,
        "premier_finale",
    )

    print("\n===== HOLDOUT 2026 =====")
    print(f"Partite: {len(holdout)}")
    print(
        f"Premier candidata: intercetta={a_finale:.6f}, "
        f"pendenza={b_finale:.6f}"
    )
    _print_metriche("Serie A v0.6.0", _metriche(holdout, "serie_a"))
    _print_metriche("Premier candidata", _metriche(holdout, "premier_finale"))
    _print_bootstrap(
        "BOOTSTRAP PREMIER CANDIDATA vs SERIE A v0.6.0",
        _bootstrap_delta(holdout, "serie_a", "premier_finale"),
    )

    print("\nINTERPRETAZIONE DEL DELTA")
    print("  delta > 0  => Premier specifica migliore")
    print("  delta < 0  => Serie A v0.6.0 migliore")
    print("  CI che include 0 => differenza non conclusiva")
    print("\nNessun coefficiente viene promosso automaticamente.")


if __name__ == "__main__":
    main()
