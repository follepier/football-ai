import time
from unittest.mock import Mock, patch

import requests

import app.services.football_api as football_api
from app.services.team_data import calcola_medie_casa_trasferta


def _http_429():
    response = Mock()
    response.status_code = 429
    error = requests.HTTPError("429 Too Many Requests", response=response)
    response.raise_for_status.side_effect = error
    return response


def verify_stale_fixture_cache_survives_429():
    cached_value = {
        "competition": "serie-a",
        "data": [{"id": "cached-fixture"}],
    }
    now = time.time()

    football_api._FIXTURES_CACHE.clear()
    football_api._FIXTURES_CACHE["serie-a"] = {
        "value": cached_value,
        "saved_at": now - 1000,
        "expires_at": now - 1,
        "stale_until": now + 3600,
    }

    with patch.object(
        football_api.requests,
        "get",
        return_value=_http_429(),
    ):
        result = football_api.get_league_fixtures("serie-a")

    assert result == cached_value


def verify_optional_fixture_stats_do_not_abort_analysis_data():
    fixture = {
        "id": 123,
        "teams": {
            "home": {"name": "Inter"},
            "away": {"name": "Monza"},
        },
        "goals": {"home": 2, "away": 1},
        "corners": {"home": 7, "away": 3},
        "cards": {
            "home": {"yellow": 2},
            "away": {"yellow": 4},
        },
        "kickoff_utc": "2026-09-01T18:45:00+00:00",
        "league": {"name": "Serie A"},
    }

    with patch.object(
        football_api,
        "get_fixture_stats",
        side_effect=requests.HTTPError("429 Too Many Requests"),
    ):
        transformed = football_api.trasforma_partite_squadra(
            [fixture],
            "Inter",
        )

    assert len(transformed) == 1
    row = transformed[0]
    assert row["gol_fatti"] == 2
    assert row["corner"] == 7
    assert row["statistiche_provider_disponibili"] is False
    assert row["possesso"] is None
    assert row["tiri_in_porta"] is None
    assert row["attacchi_pericolosi"] is None


def verify_optional_averages_ignore_missing_values():
    rows = [
        {
            "casa_trasferta": "casa",
            "gol_fatti": 2,
            "gol_subiti": 1,
            "corner": 7,
            "ammonizioni": 2,
            "possesso": None,
            "tiri_in_porta": None,
            "tiri_fuori": None,
            "attacchi": None,
            "attacchi_pericolosi": None,
        },
        {
            "casa_trasferta": "casa",
            "gol_fatti": 1,
            "gol_subiti": 0,
            "corner": 5,
            "ammonizioni": 1,
            "possesso": 58,
            "tiri_in_porta": 6,
            "tiri_fuori": 8,
            "attacchi": 100,
            "attacchi_pericolosi": 45,
        },
    ]

    medie = calcola_medie_casa_trasferta(rows, "casa")

    assert medie["gol_fatti"] == 1.5
    assert medie["possesso"] == 58.0
    assert medie["possesso_campioni"] == 1
    assert medie["tiri_in_porta"] == 6.0
    assert medie["tiri_in_porta_campioni"] == 1
    assert medie["attacchi_pericolosi"] == 45.0
    assert medie["attacchi_pericolosi_campioni"] == 1


def main():
    verify_stale_fixture_cache_survives_429()
    verify_optional_fixture_stats_do_not_abort_analysis_data()
    verify_optional_averages_ignore_missing_values()
    print("PASS provider rate-limit resilience")


if __name__ == "__main__":
    main()
