from __future__ import annotations

from backtest_european_common_calibration import (
    BOOTSTRAP_REPS,
    STAGIONI_STORICHE,
    STAGIONE_HOLDOUT,
    add_raw,
    apply_affine,
    bootstrap_delta,
    build_walkforward_rows,
    fit_affine_poisson,
    metriche,
    print_bootstrap_compact as print_bootstrap,
    print_metriche,
)


LEAGUES = (
    ("serie-a", "Serie A"),
    ("premier-league", "Premier League"),
    ("la-liga", "La Liga"),
    ("bundesliga", "Bundesliga"),
    ("ligue-1", "Ligue 1"),
)

PROD_INTERCETTA = 0.214047
PROD_PENDENZA = 0.765037


def build_all_rows():
    data = {}
    for slug, name in LEAGUES:
        data[slug] = {}
        for season in (*STAGIONI_STORICHE, STAGIONE_HOLDOUT):
            rows = build_walkforward_rows(slug, season)
            add_raw(rows)
            data[slug][season] = rows
            print(f"{name:<18} {season}: {len(rows)} partite")
    return data


def rows_for(data, slugs, seasons):
    return [
        r
        for slug in slugs
        for season in seasons
        for r in data[slug][season]
    ]


def main():
    print("===== CONFRONTO TEMPORALE CORRETTO · SERIE A vs EUROPA =====")
    print("Il benchmark Serie A viene rifittato solo su stagioni precedenti.")
    print("Niente coefficienti finali 2023-2025 applicati retroattivamente al 2024/2025.")
    print(f"Bootstrap: {BOOTSTRAP_REPS} repliche")

    data = build_all_rows()
    all_slugs = tuple(slug for slug, _ in LEAGUES)

    combined_oos = []
    per_league_oos = {slug: [] for slug in all_slugs}

    print("\n===== COEFFICIENTI WALK-FORWARD =====")
    for test_season in (2024, 2025):
        train_seasons = tuple(s for s in STAGIONI_STORICHE if s < test_season)

        seriea_train = rows_for(data, ("serie-a",), train_seasons)
        europe_train = rows_for(data, all_slugs, train_seasons)

        sa_a, sa_b = fit_affine_poisson(seriea_train)
        eu_a, eu_b = fit_affine_poisson(europe_train)

        print(
            f"Test {test_season} | "
            f"SerieA: a={sa_a:.6f}, b={sa_b:.6f}, n={len(seriea_train)} | "
            f"Europa: a={eu_a:.6f}, b={eu_b:.6f}, n={len(europe_train)}"
        )

        for slug in all_slugs:
            rows = data[slug][test_season]
            apply_affine(rows, sa_a, sa_b, "seriea_walk")
            apply_affine(rows, eu_a, eu_b, "europe_walk")
            per_league_oos[slug].extend(rows)
            combined_oos.extend(rows)

    print("\n===== OOS STORICO 2024+2025 · COMBINATO =====")
    print_metriche("Serie A walk-forward", metriche(combined_oos, "seriea_walk"))
    print_metriche("Europa walk-forward", metriche(combined_oos, "europe_walk"))
    print_bootstrap(
        "BOOTSTRAP EUROPA vs SERIE A · OOS COMBINATO",
        bootstrap_delta(combined_oos, "seriea_walk", "europe_walk", seed_offset=701),
        "Europa walk-forward",
        "Serie A walk-forward",
    )

    print("\n===== OOS STORICO 2024+2025 · PER CAMPIONATO =====")
    for idx, (slug, name) in enumerate(LEAGUES, start=1):
        rows = per_league_oos[slug]
        print("\n" + "-" * 72)
        print(name.upper())
        print_metriche("Serie A walk-forward", metriche(rows, "seriea_walk"))
        print_metriche("Europa walk-forward", metriche(rows, "europe_walk"))
        print_bootstrap(
            f"BOOTSTRAP EUROPA vs SERIE A · {name}",
            bootstrap_delta(rows, "seriea_walk", "europe_walk", seed_offset=710 + idx),
            "Europa walk-forward",
            "Serie A walk-forward",
        )

    # Holdout 2026: qui entrambi i candidati possono usare tutto il 2023-2025.
    seriea_final_train = rows_for(data, ("serie-a",), STAGIONI_STORICHE)
    europe_final_train = rows_for(data, all_slugs, STAGIONI_STORICHE)
    sa_a, sa_b = fit_affine_poisson(seriea_final_train)
    eu_a, eu_b = fit_affine_poisson(europe_final_train)

    holdout = []
    for slug in all_slugs:
        rows = data[slug][STAGIONE_HOLDOUT]
        apply_affine(rows, sa_a, sa_b, "seriea_final_refit")
        apply_affine(rows, eu_a, eu_b, "europe_final")
        apply_affine(rows, PROD_INTERCETTA, PROD_PENDENZA, "prod_v060")
        holdout.extend(rows)

    print("\n===== HOLDOUT 2026 · COMBINATO =====")
    print(
        f"Serie A refit 2023-2025: a={sa_a:.6f}, b={sa_b:.6f} | "
        f"Europa 2023-2025: a={eu_a:.6f}, b={eu_b:.6f}"
    )
    print_metriche("Produzione v0.6.0", metriche(holdout, "prod_v060"))
    print_metriche("Serie A refit", metriche(holdout, "seriea_final_refit"))
    print_metriche("Europa finale", metriche(holdout, "europe_final"))
    print_bootstrap(
        "BOOTSTRAP EUROPA FINALE vs PRODUZIONE v0.6.0 · HOLDOUT",
        bootstrap_delta(holdout, "prod_v060", "europe_final", seed_offset=801),
        "Europa finale",
        "Produzione v0.6.0",
    )
    print_bootstrap(
        "BOOTSTRAP EUROPA FINALE vs SERIE A REFIT · HOLDOUT",
        bootstrap_delta(holdout, "seriea_final_refit", "europe_final", seed_offset=802),
        "Europa finale",
        "Serie A refit",
    )

    print("\n===== DECISIONE =====")
    print("Questo script non promuove automaticamente alcun coefficiente.")
    print("La scelta va fatta privilegiando OOS walk-forward e conferma holdout 2026.")


if __name__ == "__main__":
    main()
