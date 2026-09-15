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


def saved_shots(shots):
    return sum(1 for shot in shots if shot.get("result") == "SavedShot")


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


def _round_or_none(value, digits=2):
    if value is None:
        return None
    return round(float(value), digits)


def audit_competition(competition, sample_matches=10):
    slug = competition["slug"]
    data = get_understat_league_data(slug)

    teams = data.get("teams", {})
    team_records = list(teams.values()) if isinstance(teams, dict) else teams

    core_coverage = []
    field_tilt_coverage = []
    field_tilt_values = []

    for team in team_records or []:
        title = team.get("title")
        if not title:
            continue

        metrics = calculate_team_advanced_metrics_from_league_data(
            data,
            title,
        )
        core_coverage.append(
            all(
                metrics.get(key) is not None
                for key in (
                    "ppda",
                    "expected_assists_per_match",
                    "key_passes_per_match",
                )
            )
        )

        has_field_tilt = metrics.get("field_tilt_proxy") is not None
        field_tilt_coverage.append(has_field_tilt)
        if has_field_tilt:
            field_tilt_values.append(metrics["field_tilt_proxy"])

    dates = [
        row
        for row in data.get("dates", [])
        if row.get("isResult") and row.get("id")
    ]
    dates.sort(key=lambda row: row.get("datetime", ""), reverse=True)

    saves_inside_samples = []
    saves_total_samples = []

    for match in dates[:sample_matches]:
        shots = fetch_match_shots(match["id"])

        # Home goalkeeper faces away shots; away goalkeeper faces home shots.
        goalkeeper_shot_sets = [shots["away"], shots["home"]]
        for faced_shots in goalkeeper_shot_sets:
            saves_inside_samples.append(saved_shots_inside_box(faced_shots))
            saves_total_samples.append(saved_shots(faced_shots))

    core_coverage_rate = (
        0.0
        if not core_coverage
        else 100 * sum(core_coverage) / len(core_coverage)
    )
    field_tilt_coverage_rate = (
        0.0
        if not field_tilt_coverage
        else 100 * sum(field_tilt_coverage) / len(field_tilt_coverage)
    )

    total_saves = sum(saves_total_samples)
    total_inside_saves = sum(saves_inside_samples)

    return {
        "competition": competition["name"],
        "teams": len(core_coverage),
        "core_coverage_pct": round(core_coverage_rate, 1),
        "field_tilt_coverage_pct": round(field_tilt_coverage_rate, 1),
        "field_tilt_min": min(field_tilt_values) if field_tilt_values else None,
        "field_tilt_max": max(field_tilt_values) if field_tilt_values else None,
        "field_tilt_mean": (
            round(statistics.mean(field_tilt_values), 2)
            if field_tilt_values
            else None
        ),
        "saves_in_box_sample_mean": (
            round(statistics.mean(saves_inside_samples), 2)
            if saves_inside_samples
            else None
        ),
        "saves_in_box_sample_median": (
            _round_or_none(statistics.median(saves_inside_samples))
            if saves_inside_samples
            else None
        ),
        "saves_in_box_sample_min": (
            min(saves_inside_samples) if saves_inside_samples else None
        ),
        "saves_in_box_sample_max": (
            max(saves_inside_samples) if saves_inside_samples else None
        ),
        "saves_inside_box_share_of_all_saves_pct": (
            None
            if total_saves <= 0
            else round(100 * total_inside_saves / total_saves, 1)
        ),
        "saves_sample_goalkeepers": len(saves_inside_samples),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sample-matches",
        type=int,
        default=10,
        help="Recent finished matches sampled per competition for saves audit.",
    )
    args = parser.parse_args()

    print("Advanced metrics live audit")
    print("Field Tilt remains an explicitly labelled proxy based on deep-completion share.")
    print("Saves-in-box remains audit-only pending broader coordinate validation.\n")

    for competition in list_competitions():
        result = audit_competition(
            competition,
            sample_matches=max(1, min(args.sample_matches, 20)),
        )
        print(result)


if __name__ == "__main__":
    main()
