from pathlib import Path
from tempfile import TemporaryDirectory

from app.services import analysis_cache


def provider_fixture(fixture_id, kickoff_ts, home, away):
    return {
        "id": fixture_id,
        "status": "finished",
        "kickoff_ts": kickoff_ts,
        "teams": {
            "home": {"name": home},
            "away": {"name": away},
        },
    }


def main():
    with TemporaryDirectory() as tmp_dir:
        original_dir = analysis_cache.ANALYSIS_CACHE_DIR
        analysis_cache.ANALYSIS_CACHE_DIR = Path(tmp_dir)
        try:
            key = analysis_cache.build_analysis_cache_key(
                "serie-a",
                "Inter",
                "Milan",
                season=2026,
            )
            same_key = analysis_cache.build_analysis_cache_key(
                "serie-a",
                " inter ",
                "milan",
                season=2026,
            )
            next_season_key = analysis_cache.build_analysis_cache_key(
                "serie-a",
                "Inter",
                "Milan",
                season=2027,
            )

            assert key == same_key
            assert key != next_season_key
            assert analysis_cache.load_cached_analysis(key) is None

            analysis_cache.record_provider_fixture_snapshot(
                "serie-a",
                [
                    provider_fixture(1, 100, "Inter", "Roma"),
                    provider_fixture(2, 120, "Milan", "Napoli"),
                ],
                observed_at="1970-01-01T00:03:00+00:00",
            )
            freshness = analysis_cache.get_freshness_snapshot(
                "serie-a",
                "Inter",
                "Milan",
            )
            assert freshness["home_latest_finished_ts"] == 100
            assert freshness["away_latest_finished_ts"] == 120

            response = {
                "status": "success",
                "partita": "Inter vs Milan",
                "analisi": {"gol_attesi_casa": 1.55},
            }
            saved_at = analysis_cache.save_cached_analysis(
                key,
                response,
                metadata={
                    "competition": "serie-a",
                    "home_team": "Inter",
                    "away_team": "Milan",
                    "kickoff_ts": 1000,
                    "freshness": freshness,
                    "provisional": False,
                },
                saved_at="1970-01-01T00:04:00+00:00",
            )
            assert saved_at

            cached = analysis_cache.load_cached_analysis(key)
            assert cached is not None
            assert cached["saved_at"] == saved_at
            assert cached["response"] == response

            state = analysis_cache.evaluate_cached_analysis(
                cached,
                "serie-a",
                "Inter",
                "Milan",
                kickoff_ts=1000,
                now_ts=500,
            )
            assert state == {
                "valid": True,
                "frozen": False,
                "reason": None,
            }

            # Un nuovo risultato dell'Inter rende obsoleta la previsione futura.
            analysis_cache.record_provider_fixture_snapshot(
                "serie-a",
                [provider_fixture(3, 200, "Inter", "Juventus")],
                observed_at="1970-01-01T00:05:00+00:00",
            )
            stale = analysis_cache.evaluate_cached_analysis(
                cached,
                "serie-a",
                "Inter",
                "Milan",
                kickoff_ts=1000,
                now_ts=500,
            )
            assert stale["valid"] is False
            assert stale["frozen"] is False
            assert stale["reason"] == "new_finished_match"

            # Dopo il kickoff la previsione salvata resta congelata, anche se
            # esistono dati piu' nuovi: non va riscritta retroattivamente.
            frozen = analysis_cache.evaluate_cached_analysis(
                cached,
                "serie-a",
                "Inter",
                "Milan",
                kickoff_ts=1000,
                now_ts=1200,
            )
            assert frozen == {
                "valid": True,
                "frozen": True,
                "reason": None,
            }

            # Una copia restituita al chiamante deve restare isolata dal file.
            cached["response"]["analisi"]["gol_attesi_casa"] = 99
            cached_again = analysis_cache.load_cached_analysis(key)
            assert cached_again["response"]["analisi"]["gol_attesi_casa"] == 1.55

            # Understat aggiorna lo stesso indice di freshness senza inventare
            # dati provider-only.
            analysis_cache.record_understat_snapshot(
                "serie-a",
                {
                    "dates": [
                        {
                            "isResult": True,
                            "datetime": "1970-01-01T00:04:10+00:00",
                            "h": {"title": "Milan"},
                            "a": {"title": "Atalanta"},
                        }
                    ]
                },
                observed_at="1970-01-01T00:06:00+00:00",
            )
            understat_freshness = analysis_cache.get_freshness_snapshot(
                "serie-a",
                "Inter",
                "Milan",
            )
            assert understat_freshness["away_latest_finished_ts"] == 250
        finally:
            analysis_cache.ANALYSIS_CACHE_DIR = original_dir

    print("PASS automatic persistent analysis cache")


if __name__ == "__main__":
    main()
