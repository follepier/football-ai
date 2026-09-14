import unittest
from unittest.mock import patch

import requests

from app.services import football_api as api


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def make_fixture(
    fixture_id,
    home,
    away,
    home_goals=0,
    away_goals=0,
    kickoff_ts=1,
    status="finished",
):
    return {
        "id": fixture_id,
        "status": status,
        "kickoff_ts": kickoff_ts,
        "kickoff_utc": "2026-01-01T00:00:00+00:00",
        "teams": {
            "home": {"name": home},
            "away": {"name": away},
        },
        "goals": {
            "home": home_goals,
            "away": away_goals,
        },
        "corners": {
            "home": 5,
            "away": 3,
        },
        "cards": {
            "home": {"yellow": 2},
            "away": {"yellow": 1},
        },
        "league": {"name": "Serie A"},
    }


class FootballApiTests(unittest.TestCase):
    def setUp(self):
        api._FIXTURES_CACHE["value"] = None
        api._FIXTURES_CACHE["expires_at"] = 0.0
        api._FIXTURE_STATS_CACHE.clear()

    def tearDown(self):
        api._FIXTURES_CACHE["value"] = None
        api._FIXTURES_CACHE["expires_at"] = 0.0
        api._FIXTURE_STATS_CACHE.clear()

    def test_team_alias_matching_does_not_confuse_milan_and_inter(self):
        cases = [
            ("inter", "Inter Milan", True),
            ("inter", "AC Milan", False),
            ("milan", "AC Milan", True),
            ("milan", "Inter Milan", False),
            ("internazionale", "Inter Milan", True),
            ("ac milan", "AC Milan", True),
            ("parma", "Parma Calcio 1913", True),
        ]

        for query, provider_name, expected in cases:
            with self.subTest(query=query, provider_name=provider_name):
                self.assertEqual(
                    api.stessa_squadra(query, provider_name),
                    expected,
                )

    def test_name_normalization_handles_case_whitespace_and_punctuation(self):
        cases = [
            ("  AC   Milan ", "AC Milan"),
            ("A.C. Milan", "AC Milan"),
            ("INTER-MILAN", "Inter Milan"),
            ("Parma_Calcio_1913", "Parma Calcio 1913"),
        ]

        for query, provider_name in cases:
            with self.subTest(query=query, provider_name=provider_name):
                self.assertTrue(api.stessa_squadra(query, provider_name))

    def test_get_team_last_matches_filters_exact_team_after_normalization(self):
        fixtures = [
            make_fixture(
                101,
                "Inter Milan",
                "Napoli",
                home_goals=3,
                away_goals=2,
                kickoff_ts=3,
            ),
            make_fixture(
                202,
                "AC Milan",
                "Venezia",
                home_goals=2,
                away_goals=0,
                kickoff_ts=2,
            ),
            make_fixture(
                303,
                "Cagliari",
                "Inter Milan",
                home_goals=0,
                away_goals=1,
                kickoff_ts=1,
            ),
        ]

        with patch.object(
            api,
            "get_serie_a_fixtures",
            return_value={"data": fixtures},
        ):
            milan = api.get_team_last_matches("milan", limit=5)
            inter = api.get_team_last_matches("inter", limit=5)

        self.assertEqual([p["id"] for p in milan], [202])
        self.assertEqual([p["id"] for p in inter], [101, 303])

    def test_get_team_last_matches_ignores_unfinished_matches(self):
        fixtures = [
            make_fixture(
                1,
                "AC Milan",
                "Napoli",
                kickoff_ts=2,
                status="scheduled",
            ),
            make_fixture(
                2,
                "AC Milan",
                "Roma",
                kickoff_ts=1,
                status="finished",
            ),
        ]

        with patch.object(
            api,
            "get_serie_a_fixtures",
            return_value={"data": fixtures},
        ):
            result = api.get_team_last_matches("milan")

        self.assertEqual([p["id"] for p in result], [2])

    def test_transform_uses_correct_side_for_milan(self):
        fixture = make_fixture(
            404,
            "Torino",
            "AC Milan",
            home_goals=1,
            away_goals=2,
        )

        fixture["corners"] = {
            "home": 7,
            "away": 4,
        }
        fixture["cards"] = {
            "home": {"yellow": 2},
            "away": {"yellow": 1},
        }

        stats = {
            "possession": {
                "home": 48,
                "away": 52,
            },
            "shots_on_target": {
                "home": 3,
                "away": 4,
            },
            "shots_off_target": {
                "home": 8,
                "away": 6,
            },
            "attacks": {
                "home": 80,
                "away": 90,
            },
            "dangerous_attacks": {
                "home": 30,
                "away": 40,
            },
        }

        with patch.object(
            api,
            "get_fixture_stats",
            return_value=stats,
        ):
            transformed = api.trasforma_partite_squadra(
                [fixture],
                "milan",
            )

        self.assertEqual(len(transformed), 1)
        row = transformed[0]
        self.assertEqual(row["avversario"], "Torino")
        self.assertEqual(row["casa_trasferta"], "trasferta")
        self.assertEqual(row["gol_fatti"], 2)
        self.assertEqual(row["gol_subiti"], 1)
        self.assertEqual(row["corner"], 4)
        self.assertEqual(row["ammonizioni"], 1)
        self.assertEqual(row["possesso"], 52)
        self.assertEqual(row["tiri_in_porta"], 4)
        self.assertEqual(row["tiri_fuori"], 6)
        self.assertEqual(row["attacchi"], 90)
        self.assertEqual(row["attacchi_pericolosi"], 40)

    def test_transform_skips_foreign_fixture_without_fetching_stats(self):
        fixture = make_fixture(
            405,
            "Inter Milan",
            "Napoli",
            home_goals=2,
            away_goals=1,
        )

        with patch.object(api, "get_fixture_stats") as get_stats:
            transformed = api.trasforma_partite_squadra(
                [fixture],
                "milan",
            )

        self.assertEqual(transformed, [])
        get_stats.assert_not_called()

    def test_fixture_list_cache_reuses_http_response(self):
        fixture = make_fixture(
            505,
            "Inter Milan",
            "Napoli",
            home_goals=2,
            away_goals=1,
        )
        calls = []

        def fake_get(url, headers=None, params=None, timeout=None):
            calls.append((url, params))
            return FakeResponse({"data": [fixture]})

        with patch.object(api.requests, "get", side_effect=fake_get):
            first = api.get_serie_a_fixtures()
            second = api.get_team_last_matches("inter")
            average = api.calcola_media_gol_campionato()

        self.assertEqual(len(calls), 1)
        self.assertEqual(first["data"][0]["id"], 505)
        self.assertEqual([p["id"] for p in second], [505])
        self.assertEqual(average, 1.5)

    def test_fixture_list_cache_expires_after_ttl(self):
        fixture = make_fixture(506, "Inter Milan", "Napoli")
        calls = []

        def fake_get(url, headers=None, params=None, timeout=None):
            calls.append((url, params))
            return FakeResponse({"data": [fixture]})

        with patch.object(api.requests, "get", side_effect=fake_get), patch.object(
            api.time,
            "monotonic",
            side_effect=[0.0, 0.0, 61.0, 61.0],
        ):
            api.get_serie_a_fixtures()
            api.get_serie_a_fixtures()

        self.assertEqual(len(calls), 2)

    def test_fixture_list_pagination_stops_after_short_page(self):
        calls = []
        page_one = [
            make_fixture(i, "Inter Milan", "Napoli")
            for i in range(1, 101)
        ]
        page_two = [make_fixture(101, "Roma", "Lazio")]

        def fake_get(url, headers=None, params=None, timeout=None):
            calls.append(params["page"])
            payload = page_one if params["page"] == 1 else page_two
            return FakeResponse({"data": payload})

        with patch.object(api.requests, "get", side_effect=fake_get):
            result = api.get_serie_a_fixtures()

        self.assertEqual(calls, [1, 2])
        self.assertEqual(len(result["data"]), 101)

    def test_fixture_list_http_failure_is_not_cached(self):
        calls = []

        class FailingResponse:
            def raise_for_status(self):
                raise requests.HTTPError("429")

            def json(self):
                return {}

        def fake_get(url, headers=None, params=None, timeout=None):
            calls.append(url)
            return FailingResponse()

        with patch.object(api.requests, "get", side_effect=fake_get):
            with self.assertRaises(requests.HTTPError):
                api.get_serie_a_fixtures()
            with self.assertRaises(requests.HTTPError):
                api.get_serie_a_fixtures()

        self.assertEqual(len(calls), 2)
        self.assertIsNone(api._FIXTURES_CACHE["value"])

    def test_fixture_stats_cache_reuses_http_response(self):
        calls = []
        payload = {
            "data": {
                "statistics": {
                    "possession": {
                        "home": 60,
                        "away": 40,
                    }
                }
            }
        }

        def fake_get(url, headers=None, params=None, timeout=None):
            calls.append((url, params))
            return FakeResponse(payload)

        with patch.object(api.requests, "get", side_effect=fake_get):
            first = api.get_fixture_stats(606)
            second = api.get_fixture_stats(606)

        self.assertEqual(len(calls), 1)
        self.assertEqual(first, second)
        self.assertEqual(first["possession"]["home"], 60)

    def test_fixture_stats_cache_is_separate_per_fixture(self):
        calls = []

        def fake_get(url, headers=None, params=None, timeout=None):
            calls.append(url)
            fixture_id = int(url.rsplit("/", 1)[-1])
            return FakeResponse({
                "data": {
                    "statistics": {
                        "fixture_id": fixture_id,
                    }
                }
            })

        with patch.object(api.requests, "get", side_effect=fake_get):
            first = api.get_fixture_stats(700)
            second = api.get_fixture_stats(701)
            again = api.get_fixture_stats(700)

        self.assertEqual(len(calls), 2)
        self.assertEqual(first["fixture_id"], 700)
        self.assertEqual(second["fixture_id"], 701)
        self.assertEqual(again["fixture_id"], 700)

    def test_fixture_stats_cache_expires_after_ttl(self):
        calls = []
        payload = {"data": {"statistics": {"ok": True}}}

        def fake_get(url, headers=None, params=None, timeout=None):
            calls.append(url)
            return FakeResponse(payload)

        with patch.object(api.requests, "get", side_effect=fake_get), patch.object(
            api.time,
            "monotonic",
            side_effect=[0.0, 0.0, 3601.0, 3601.0],
        ):
            api.get_fixture_stats(800)
            api.get_fixture_stats(800)

        self.assertEqual(len(calls), 2)

    def test_calculate_league_average_uses_only_finished_matches(self):
        fixtures = [
            make_fixture(
                1,
                "Inter Milan",
                "Napoli",
                home_goals=3,
                away_goals=1,
                status="finished",
            ),
            make_fixture(
                2,
                "Roma",
                "Lazio",
                home_goals=10,
                away_goals=10,
                status="scheduled",
            ),
        ]

        with patch.object(
            api,
            "get_serie_a_fixtures",
            return_value={"data": fixtures},
        ):
            average = api.calcola_media_gol_campionato()

        self.assertEqual(average, 2.0)

    def test_understat_matching_does_not_confuse_milan_and_inter(self):
        payload = {
            "dates": [
                {
                    "isResult": True,
                    "datetime": "2026-09-01 20:00:00",
                    "h": {"title": "Inter"},
                    "a": {"title": "Napoli"},
                    "xG": {"h": "2.1", "a": "1.0"},
                },
                {
                    "isResult": True,
                    "datetime": "2026-09-02 20:00:00",
                    "h": {"title": "AC Milan"},
                    "a": {"title": "Roma"},
                    "xG": {"h": "1.7", "a": "0.9"},
                },
            ]
        }

        with patch.object(
            api.requests,
            "get",
            return_value=FakeResponse(payload),
        ):
            milan = api.get_understat_team_matches("milan", limit=5)
            inter = api.get_understat_team_matches("inter", limit=5)

        self.assertEqual(len(milan), 1)
        self.assertEqual(milan[0]["avversario"], "Roma")
        self.assertEqual(milan[0]["xg_fatti"], 1.7)
        self.assertEqual(len(inter), 1)
        self.assertEqual(inter[0]["avversario"], "Napoli")
        self.assertEqual(inter[0]["xg_fatti"], 2.1)


if __name__ == "__main__":
    unittest.main()
