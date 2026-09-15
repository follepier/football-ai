from datetime import datetime, timezone

from app.services.understat_fallback import (
    build_understat_recent_form_from_league_data,
    build_understat_upcoming_from_league_data,
)


def main():
    league_data = {
        "dates": [
            {
                "id": "100",
                "isResult": True,
                "datetime": "2026-09-10 19:00:00",
                "h": {"title": "Liverpool"},
                "a": {"title": "Manchester City"},
                "goals": {"h": "2", "a": "1"},
            },
            {
                "id": "101",
                "isResult": True,
                "datetime": "2026-09-05 14:00:00",
                "h": {"title": "Manchester City"},
                "a": {"title": "Arsenal"},
                "goals": {"h": "3", "a": "0"},
            },
            {
                "id": "102",
                "isResult": False,
                "datetime": "2026-09-20 16:30:00",
                "h": {"title": "Manchester City"},
                "a": {"title": "Chelsea"},
                "goals": {"h": None, "a": None},
            },
        ]
    }

    recent = build_understat_recent_form_from_league_data(
        league_data,
        "Man City",
        "Premier League",
        limit=5,
    )

    assert len(recent) == 2
    assert recent[0]["avversario"] == "Liverpool"
    assert recent[0]["gol_fatti"] == 1
    assert recent[0]["gol_subiti"] == 2
    assert recent[0]["corner"] is None
    assert recent[0]["possesso"] is None
    assert recent[0]["dati_parziali"] is True

    upcoming = build_understat_upcoming_from_league_data(
        league_data,
        "Premier League",
        limit=20,
        now=datetime(2026, 9, 15, tzinfo=timezone.utc),
    )

    assert len(upcoming) == 1
    assert upcoming[0]["home"] == "Manchester City"
    assert upcoming[0]["away"] == "Chelsea"
    assert upcoming[0]["data_fallback"] is True
    assert upcoming[0]["source"] == "Understat"

    print("PASS Understat fallback deterministic logic")


if __name__ == "__main__":
    main()
