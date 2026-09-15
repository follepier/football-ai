import argparse
import statistics

import requests

from app.services.advanced_stats import (
    calculate_team_advanced_metrics_from_league_data,
)
from app.services.competitions import list_competitions
from app.services.football_api import get_understat_league_data


UNDERSTAT_MATCH_URL = "https://understat.com/getMatchData/{match_id}"
UNDERSTAT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://understat.com/",
}


def is_inside_penalty_area(shot):
    """Audit geometry for Understat normalized shot coordinates.

    Understat uses normalized pitch coordinates. We intentionally keep this
    as an audit-only approximation until coverage is checked on live data.
    """
    try:
        x = float(shot.get("X"))
        y = float(shot.get("Y"))
    except (TypeError, ValueError):
        return False

    return x >= 0.833 and 0.211 <= y <= 0.789


def saved_shots_inside_box(shots):
    return sum(
        1
        for shot in shots
        if shot.get("result") == "SavedShot"
        and is_inside_penalty_area(shot)
    )


def fetch_match_shots(match_id):
    response = requests.get(
        UNDERSTAT_MATCH_URL.format(match_id=match_id),
        headers=UNDERSTAT_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    shots = payload.get("shots", {})
    return {
        "home": shots.get("h", []),
        "away": shots.get("a", []),
    }


def audit_competition(competition, sample_matches=3):
    slug = competition["slug"]
    data = get_understat_league_data(slug)

    teams = data.get("teams", {})
    team_records = list(teams.values()) if isinstance(teams, dict) else teams

    coverage = []
    field_tilt_values = []

    for team in team_records or []:
        title = team.get("title")
        if not title:
            continue

        metrics = calculate_team_advanced_metrics_from_league_data(
            data,
            title,
        )
        coverage.append(
            all(
                metrics.get(key) is not None
                for key in (
                    "ppda",
                    "expected_assists_per_match",
                    "key_passes_per_match",
                )
            )
        )
        if metrics.get("field_tilt_proxy") is not None:
            field_tilt_values.append(metrics["field_tilt_proxy"])

    dates = [
        row
        for row in data.get("dates", [])
        if row.get("isResult") and row.get("id")
    ]
    dates.sort(key=lambda row: row.get("datetime", ""), reverse=True)

    saves_samples = []
    for match in dates[:sample_matches]:
        shots = fetch_match_shots(match["id"])
        # Home goalkeeper saves away shots; away goalkeeper saves home shots.
        saves_samples.extend(
            [
                saved_shots_inside_box(shots["away"]),
                saved_shots_inside_box(shots["home"]),
            ]
        )

    coverage_rate = (
        0.0
        if not coverage
        else 100 * sum(coverage) / len(coverage)
    )

    return {
        "competition": competition["name"],
        "teams": len(coverage),
        "core_coverage_pct": round(coverage_rate, 1),
        "field_tilt_min": min(field_tilt_values) if field_tilt_values else None,
        "field_tilt_max": max(field_tilt_values) if field_tilt_values else None,
        "field_tilt_mean": (
            round(statistics.mean(field_tilt_values), 2)
            if field_tilt_values
            else None
        ),
        "saves_in_box_sample_mean": (
            round(statistics.mean(saves_samples), 2)
            if saves_samples
            else None
        ),
        "saves_sample_goalkeepers": len(saves_samples),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sample-matches",
        type=int,
        default=3,
        help="Recent finished matches sampled per competition for saves audit.",
    )
    args = parser.parse_args()

    print("Advanced metrics live audit")
    print("Field Tilt remains a proxy based on deep-completion share.")
    print("Saves-in-box remains audit-only pending coordinate validation.\n")

    for competition in list_competitions():
        result = audit_competition(
            competition,
            sample_matches=max(1, min(args.sample_matches, 5)),
        )
        print(result)


if __name__ == "__main__":
    main()
