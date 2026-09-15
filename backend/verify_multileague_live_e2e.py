from __future__ import annotations

import math
import sys
import time

from fastapi.testclient import TestClient

from app.main import app
from app.services.competitions import COMPETITIONS
from app.services.football_api import get_league_fixtures


EXPECTED_VERSION = "0.7.0"
EXPECTED_A = 0.214047
EXPECTED_B = 0.765037
TOL = 1e-6

LEAGUES = (
    "serie-a",
    "premier-league",
    "la-liga",
    "bundesliga",
    "ligue-1",
)


def latest_finished_fixture(slug: str):
    fixtures = get_league_fixtures(slug).get("data", [])
    finished = [
        f
        for f in fixtures
        if f.get("status") == "finished"
        and f.get("teams", {}).get("home", {}).get("name")
        and f.get("teams", {}).get("away", {}).get("name")
    ]

    if not finished:
        raise RuntimeError(f"Nessuna partita finita disponibile per {slug}")

    finished.sort(key=lambda f: f.get("kickoff_ts", 0), reverse=True)
    return finished[0]


def approx_equal(a, b, tol=TOL):
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=tol)


def assert_probability_block(name: str, block: dict, keys: tuple[str, ...]):
    values = [float(block[k]) for k in keys]
    if any(v < 0 or v > 100 for v in values):
        raise AssertionError(f"{name}: probabilita fuori range: {values}")

    total = sum(values)
    if not math.isclose(total, 100.0, rel_tol=0.0, abs_tol=0.08):
        raise AssertionError(f"{name}: somma={total:.4f}, atteso circa 100")


def validate_analysis(slug: str, payload: dict):
    if payload.get("status") != "success":
        raise AssertionError("status risposta != success")

    competition = payload.get("competizione", {})
    if competition.get("slug") != slug:
        raise AssertionError(
            f"competizione errata: {competition.get('slug')} != {slug}"
        )

    model = payload.get("modello", {})
    if model.get("validato") is not True:
        raise AssertionError("modello non marcato come validato")
    if model.get("stato") != "validato":
        raise AssertionError(f"stato modello inatteso: {model.get('stato')}")

    analysis = payload.get("analisi", {})
    calibration = analysis.get("calibrazione_xg", {})

    if not approx_equal(calibration.get("intercetta"), EXPECTED_A):
        raise AssertionError(
            f"intercetta={calibration.get('intercetta')} != {EXPECTED_A}"
        )
    if not approx_equal(calibration.get("pendenza"), EXPECTED_B):
        raise AssertionError(
            f"pendenza={calibration.get('pendenza')} != {EXPECTED_B}"
        )
    if calibration.get("validata") is not True:
        raise AssertionError("calibrazione xG non marcata come validata")

    for key in (
        "gol_attesi_casa",
        "gol_attesi_ospite",
        "gol_attesi_totali",
        "gol_attesi_casa_raw",
        "gol_attesi_ospite_raw",
    ):
        value = float(analysis[key])
        if not math.isfinite(value) or value < 0:
            raise AssertionError(f"{key} non valido: {value}")

    assert_probability_block("1X2", analysis["1x2"], ("1", "X", "2"))

    # Le tre doppie chance sono mercati distinti e non devono sommare a 100.
    for key in ("1X", "X2", "12"):
        value = float(analysis["doppia_chance"][key])
        if value < 0 or value > 100:
            raise AssertionError(f"Doppia chance {key} fuori range: {value}")

    ou = analysis["over_under"]
    for over_key, under_key in (
        ("over_1_5", "under_1_5"),
        ("over_2_5", "under_2_5"),
        ("over_3_5", "under_3_5"),
    ):
        assert_probability_block(
            f"{over_key}/{under_key}",
            ou,
            (over_key, under_key),
        )

    assert_probability_block(
        "Gol/No Gol",
        analysis["gol_no_gol"],
        ("gol", "no_gol"),
    )

    exact = analysis.get("risultati_esatti", [])
    if len(exact) != 5:
        raise AssertionError(f"risultati esatti: {len(exact)} invece di 5")

    recent = payload.get("ultime_partite", {})
    if not recent.get("casa") or not recent.get("ospite"):
        raise AssertionError("ultime partite mancanti per una delle due squadre")

    required_match_fields = {
        "gol_fatti",
        "gol_subiti",
        "corner",
        "ammonizioni",
        "possesso",
        "tiri_in_porta",
        "tiri_fuori",
        "attacchi",
        "attacchi_pericolosi",
        "casa_trasferta",
    }

    for side in ("casa", "ospite"):
        first = recent[side][0]
        missing = required_match_fields - set(first)
        if missing:
            raise AssertionError(
                f"campi statistiche mancanti in {side}: {sorted(missing)}"
            )

    return analysis, recent


def requested_leagues():
    requested = tuple(sys.argv[1:])
    if not requested:
        return LEAGUES

    invalid = [slug for slug in requested if slug not in LEAGUES]
    if invalid:
        valid = ", ".join(LEAGUES)
        raise SystemExit(
            f"Campionato/i non valido/i: {', '.join(invalid)}\n"
            f"Valori ammessi: {valid}"
        )

    # Mantiene l'ordine richiesto eliminando eventuali duplicati.
    return tuple(dict.fromkeys(requested))


def main():
    selected_leagues = requested_leagues()
    client = TestClient(app)
    failures = []

    health = client.get("/health")
    if health.status_code != 200:
        raise SystemExit(f"FAIL /health HTTP {health.status_code}")

    health_data = health.json()
    if health_data.get("version") != EXPECTED_VERSION:
        raise SystemExit(
            f"FAIL versione health: {health_data.get('version')} != {EXPECTED_VERSION}"
        )

    print("===== FOOTBALL AI v0.7.0 · LIVE MULTI-LEAGUE E2E =====")
    print("Usa provider reale + Understat reale; nessun mock.")
    print("Una analisi live per ciascun campionato richiesto.\n")
    print(f"PASS /health version={EXPECTED_VERSION}")
    print(f"Campionati richiesti: {', '.join(selected_leagues)}\n")

    for index, slug in enumerate(selected_leagues, start=1):
        name = COMPETITIONS[slug]["name"]
        print("=" * 84)
        print(f"{name.upper()} ({slug})")
        print("=" * 84)

        try:
            teams_response = client.get(f"/competitions/{slug}/teams")
            if teams_response.status_code != 200:
                raise AssertionError(
                    f"/teams HTTP {teams_response.status_code}: "
                    f"{teams_response.text[:300]}"
                )

            teams = teams_response.json().get("squadre", [])
            if len(teams) < 16:
                raise AssertionError(f"lista squadre sospetta: {len(teams)}")

            fixture = latest_finished_fixture(slug)
            home = fixture["teams"]["home"]["name"]
            away = fixture["teams"]["away"]["name"]

            print(f"Squadre provider: {len(teams)}")
            print(f"Fixture scelta: {home} vs {away}")

            response = client.get(
                "/analyze",
                params={
                    "casa": home,
                    "ospite": away,
                    "competizione": slug,
                },
            )

            if response.status_code != 200:
                raise AssertionError(
                    f"/analyze HTTP {response.status_code}: {response.text[:500]}"
                )

            payload = response.json()
            analysis, recent = validate_analysis(slug, payload)

            one_x_two = analysis["1x2"]
            over_25 = analysis["over_under"]["over_2_5"]
            btts = analysis["gol_no_gol"]["gol"]

            print(
                "PASS analisi | "
                f"xG {analysis['gol_attesi_casa']:.2f}-"
                f"{analysis['gol_attesi_ospite']:.2f} | "
                f"1X2 {one_x_two['1']:.2f}/"
                f"{one_x_two['X']:.2f}/"
                f"{one_x_two['2']:.2f} | "
                f"O2.5 {over_25:.2f}% | "
                f"Gol {btts:.2f}%"
            )
            print(
                "PASS dati recenti | "
                f"casa={len(recent['casa'])} | "
                f"ospite={len(recent['ospite'])} | "
                "statistiche avanzate presenti"
            )
            print(
                "PASS calibrazione | "
                f"a={EXPECTED_A}, b={EXPECTED_B}, validata=True"
            )

        except Exception as exc:  # noqa: BLE001 - audit CLI: mostra il vero errore live.
            failures.append((slug, repr(exc)))
            print(f"FAIL {name}: {exc!r}")

        if index < len(selected_leagues):
            # Pausa minima: per quote provider strette e' preferibile invocare
            # questo audit su un singolo campionato per processo.
            time.sleep(1.0)

    print("\n" + "=" * 84)
    if failures:
        print(f"LIVE E2E FALLITO: {len(failures)} campionato/i con errore")
        for slug, error in failures:
            print(f"  - {slug}: {error}")
        print("Nessun errore viene mascherato o sostituito con valori zero.")
        sys.exit(1)

    print("PASS LIVE E2E: tutti i campionati richiesti")
    print("Provider, Understat, calibrazione, mercati e statistiche recenti coerenti.")


if __name__ == "__main__":
    main()
