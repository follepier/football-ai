from __future__ import annotations

from collections import defaultdict

from backtest_other_leagues_xg_calibration import (
    BOOTSTRAP_REPS,
    EPS,
    SERIE_A_INTERCETTA,
    SERIE_A_PENDENZA,
    STAGIONI_STORICHE,
    STAGIONE_HOLDOUT,
    add_raw,
    apply_affine,
    bootstrap_delta,
    build_walkforward_rows,
    fit_affine_poisson,
    metriche,
    print_metriche,
)


LEAGUES = (
    ("serie-a", "Serie A"),
    ("premier-league", "Premier League"),
    ("la-liga", "La Liga"),
    ("bundesliga", "Bundesliga"),
    ("ligue-1", "Ligue 1"),
)


def print_bootstrap_compact(title, report, candidate, base):
    print(f"\n{title}")
    print(f"Delta positivo = {candidate} migliore di {base}")
    for metrica in ("mae", "rmse", "nll"):
        r = report[metrica]
        print(
            f"  {metrica.upper():<5} "
            f"delta {r['delta']:+.6f} | "
            f"95% CI [{r['lo']:+.6f}, {r['hi']:+.6f}] | "
            f"P {r['p']:.3f}"
        )


def prepara_dati():
    dati = defaultdict(dict)

    for slug, name in LEAGUES:
        for season in (*STAGIONI_STORICHE, STAGIONE_HOLDOUT):
            rows = build_walkforward_rows(slug, season)
            for r in rows:
                r["competizione"] = slug
                r["competizione_nome"] = name
            add_raw(rows)
            apply_affine(
                rows,
                SERIE_A_INTERCETTA,
                SERIE_A_PENDENZA,
                "serie_a",
            )
            dati[slug][season] = rows

    return dati


def fit_specifiche_oos(dati):
    for slug, _ in LEAGUES:
        for test_season in (2024, 2025):
            train = [
                r
                for season in STAGIONI_STORICHE
                if season < test_season
                for r in dati[slug][season]
            ]
            a, b = fit_affine_poisson(train)
            apply_affine(
                dati[slug][test_season],
                a,
                b,
                "specifica_oos",
            )


def fit_comune_oos(dati):
    coeffs = []

    for test_season in (2024, 2025):
        train = [
            r
            for slug, _ in LEAGUES
            for season in STAGIONI_STORICHE
            if season < test_season
            for r in dati[slug][season]
        ]
        a, b = fit_affine_poisson(train)
        coeffs.append((test_season, a, b, len(train)))

        for slug, _ in LEAGUES:
            apply_affine(
                dati[slug][test_season],
                a,
                b,
                "europea_oos",
            )

    return coeffs


def fit_finali(dati):
    train_comune = [
        r
        for slug, _ in LEAGUES
        for season in STAGIONI_STORICHE
        for r in dati[slug][season]
    ]
    a_comune, b_comune = fit_affine_poisson(train_comune)

    specifiche = {}
    for slug, _ in LEAGUES:
        train = [
            r
            for season in STAGIONI_STORICHE
            for r in dati[slug][season]
        ]
        specifiche[slug] = fit_affine_poisson(train)

    for slug, _ in LEAGUES:
        holdout = dati[slug][STAGIONE_HOLDOUT]
        apply_affine(
            holdout,
            a_comune,
            b_comune,
            "europea_finale",
        )
        a_spec, b_spec = specifiche[slug]
        apply_affine(
            holdout,
            a_spec,
            b_spec,
            "specifica_finale",
        )

    return (a_comune, b_comune, len(train_comune)), specifiche


def main():
    print("===== CALIBRAZIONE EUROPEA COMUNE · AUDIT XG =====")
    print("Top 5 campionati: Serie A, Premier, La Liga, Bundesliga, Ligue 1")
    print("Walk-forward: nessun dato futuro nelle feature del match.")
    print(f"Bootstrap: {BOOTSTRAP_REPS} repliche")
    print("Nessuna modifica automatica al modello di produzione.\n")

    dati = prepara_dati()

    print("PARTITE VALUTABILI")
    for slug, name in LEAGUES:
        counts = ", ".join(
            f"{season}={len(dati[slug][season])}"
            for season in (*STAGIONI_STORICHE, STAGIONE_HOLDOUT)
        )
        print(f"  {name:<16} {counts}")

    fit_specifiche_oos(dati)
    coeffs_comuni = fit_comune_oos(dati)

    print("\n===== COEFFICIENTI EUROPEI WALK-FORWARD =====")
    for test_season, a, b, n in coeffs_comuni:
        print(
            f"Train stagioni precedenti -> Test {test_season}: "
            f"intercetta={a:.6f}, pendenza={b:.6f}, match_train={n}"
        )

    oos_tutti = []
    for slug, _ in LEAGUES:
        oos_tutti.extend(dati[slug][2024])
        oos_tutti.extend(dati[slug][2025])

    print("\n===== OOS STORICO COMBINATO · TUTTI I CAMPIONATI =====")
    print_metriche("RAW", metriche(oos_tutti, "raw_eval"))
    print_metriche("Serie A v0.6.0", metriche(oos_tutti, "serie_a"))
    print_metriche("Europea comune", metriche(oos_tutti, "europea_oos"))
    print_bootstrap_compact(
        "BOOTSTRAP EUROPEA COMUNE vs SERIE A v0.6.0 · OOS COMBINATO",
        bootstrap_delta(oos_tutti, "serie_a", "europea_oos", seed_offset=101),
        "Europea comune",
        "Serie A v0.6.0",
    )

    print("\n===== OOS 2024+2025 · PER CAMPIONATO =====")
    for idx, (slug, name) in enumerate(LEAGUES, start=1):
        rows = dati[slug][2024] + dati[slug][2025]
        print("\n" + "-" * 72)
        print(name.upper())
        print_metriche("Serie A v0.6.0", metriche(rows, "serie_a"))
        print_metriche("Europea comune", metriche(rows, "europea_oos"))
        print_metriche("Specifica lega", metriche(rows, "specifica_oos"))
        print_bootstrap_compact(
            f"Europea comune vs Serie A v0.6.0 · {name} OOS",
            bootstrap_delta(rows, "serie_a", "europea_oos", seed_offset=120 + idx),
            "Europea comune",
            "Serie A v0.6.0",
        )
        print_bootstrap_compact(
            f"Specifica vs Europea comune · {name} OOS",
            bootstrap_delta(rows, "europea_oos", "specifica_oos", seed_offset=140 + idx),
            "Specifica lega",
            "Europea comune",
        )

    (a_comune, b_comune, n_train), specifiche = fit_finali(dati)

    print("\n===== CANDIDATO EUROPEO FINALE · FIT 2023-2025 =====")
    print(
        f"Europea comune: intercetta={a_comune:.6f}, "
        f"pendenza={b_comune:.6f}, match_train={n_train}"
    )
    print("Coefficienti specifici di confronto:")
    for slug, name in LEAGUES:
        a, b = specifiche[slug]
        print(f"  {name:<16} intercetta={a:.6f}, pendenza={b:.6f}")

    holdout_tutti = [
        r
        for slug, _ in LEAGUES
        for r in dati[slug][STAGIONE_HOLDOUT]
    ]

    print(f"\n===== HOLDOUT {STAGIONE_HOLDOUT} COMBINATO =====")
    print(f"Partite: {len(holdout_tutti)}")
    print_metriche("RAW", metriche(holdout_tutti, "raw_eval"))
    print_metriche("Serie A v0.6.0", metriche(holdout_tutti, "serie_a"))
    print_metriche("Europea comune", metriche(holdout_tutti, "europea_finale"))
    print_bootstrap_compact(
        "BOOTSTRAP EUROPEA COMUNE vs SERIE A v0.6.0 · HOLDOUT COMBINATO",
        bootstrap_delta(
            holdout_tutti,
            "serie_a",
            "europea_finale",
            seed_offset=201,
        ),
        "Europea comune",
        "Serie A v0.6.0",
    )

    print(f"\n===== HOLDOUT {STAGIONE_HOLDOUT} · PER CAMPIONATO =====")
    for idx, (slug, name) in enumerate(LEAGUES, start=1):
        rows = dati[slug][STAGIONE_HOLDOUT]
        print("\n" + "-" * 72)
        print(f"{name.upper()} · {len(rows)} partite")
        print_metriche("Serie A v0.6.0", metriche(rows, "serie_a"))
        print_metriche("Europea comune", metriche(rows, "europea_finale"))
        print_metriche("Specifica lega", metriche(rows, "specifica_finale"))
        print_bootstrap_compact(
            f"Europea comune vs Serie A v0.6.0 · {name} HOLDOUT",
            bootstrap_delta(
                rows,
                "serie_a",
                "europea_finale",
                seed_offset=220 + idx,
            ),
            "Europea comune",
            "Serie A v0.6.0",
        )
        print_bootstrap_compact(
            f"Specifica vs Europea comune · {name} HOLDOUT",
            bootstrap_delta(
                rows,
                "europea_finale",
                "specifica_finale",
                seed_offset=240 + idx,
            ),
            "Specifica lega",
            "Europea comune",
        )

    print("\n===== INTERPRETAZIONE =====")
    print("1) Il candidato europeo va valutato prima sul confronto OOS storico.")
    print("2) L'holdout 2026 resta conferma esterna, non criterio unico di scelta.")
    print("3) Una lega specifica viene preferita solo con vantaggio ripetuto e robusto.")
    print("4) Nessun coefficiente viene promosso automaticamente.")


if __name__ == "__main__":
    main()
