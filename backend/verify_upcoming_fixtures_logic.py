from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.upcoming_fixtures import get_upcoming_fixtures


def make_fixture(fixture_id, kickoff_ts, home, away, status="scheduled"):
    return {
        "id": fixture_id,
        "kickoff_ts": kickoff_ts,
        "kickoff_utc": datetime.fromtimestamp(
            kickoff_ts,
            tz=timezone.utc,
        ).isoformat(),
        "status": status,
        "teams": {
            "home": {"name": home},
            "away": {"name": away},
        },
        "league": {"name": "Serie A"},
    }


def verify_service():
    now = datetime.now(timezone.utc).timestamp()
    fixtures = [
        make_fixture(10, now - 3600, "Old Home", "Old Away", status="finished"),
        make_fixture(30, now + 7200, "Later Home", "Later Away"),
        make_fixture(20, now + 3600, "Soon Home", "Soon Away"),
        make_fixture(20, now + 3600, "Soon Home", "Soon Away"),
        {
            "id": 40,
            "kickoff_ts": now + 1800,
            "teams": {"home": {"name": "Broken"}, "away": {}},
        },
    ]

    with patch(
        "app.services.upcoming_fixtures.get_league_fixtures",
        return_value={"competition": "serie-a", "data": fixtures},
    ):
        result = get_upcoming_fixtures("serie-a", limit=2)

    assert [item["id"] for item in result] == [20, 30], result
    assert result[0]["home"] == "Soon Home"
    assert result[0]["away"] == "Soon Away"
    assert result[0]["kickoff_ts"] < result[1]["kickoff_ts"]
    print("PASS upcoming service: filtra, deduplica, ordina e limita")


def verify_endpoint():
    client = TestClient(app)
    sample = [
        {
            "id": 99,
            "kickoff_ts": 9999999999.0,
            "kickoff_utc": "2286-11-20T17:46:39+00:00",
            "status": "scheduled",
            "home": "Inter Milan",
            "away": "AC Milan",
            "league": "Serie A",
        }
    ]

    with patch("app.main.get_upcoming_fixtures", return_value=sample):
        response = client.get("/competitions/serie-a/fixtures/upcoming?limit=10")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "success"
    assert data["competizione"]["slug"] == "serie-a"
    assert data["partite"] == sample

    invalid_limit = client.get("/competitions/serie-a/fixtures/upcoming?limit=0")
    assert invalid_limit.status_code == 400

    invalid_competition = client.get("/competitions/non-esiste/fixtures/upcoming")
    assert invalid_competition.status_code == 404

    print("PASS upcoming endpoint: schema e validazioni")


if __name__ == "__main__":
    verify_service()
    verify_endpoint()
    print("PASS upcoming fixtures regression verification")
