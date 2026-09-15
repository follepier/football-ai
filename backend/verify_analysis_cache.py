from tempfile import TemporaryDirectory
from pathlib import Path

from app.services import analysis_cache


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

            response = {
                "status": "success",
                "partita": "Inter vs Milan",
                "analisi": {"gol_attesi_casa": 1.55},
            }
            saved_at = analysis_cache.save_cached_analysis(key, response)
            assert saved_at

            cached = analysis_cache.load_cached_analysis(key)
            assert cached is not None
            assert cached["saved_at"] == saved_at
            assert cached["response"] == response

            cached["response"]["analisi"]["gol_attesi_casa"] = 99
            cached_again = analysis_cache.load_cached_analysis(key)
            assert cached_again["response"]["analisi"]["gol_attesi_casa"] == 1.55
        finally:
            analysis_cache.ANALYSIS_CACHE_DIR = original_dir

    print("PASS persistent analysis cache")


if __name__ == "__main__":
    main()
