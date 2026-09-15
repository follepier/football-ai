import math

import requests

from app.services.advanced_stats import (
    _get_match_shots,
    _recent_finished_team_matches,
    _round_or_none,
    _shot_coordinates,
    _to_float,
)
from app.services.football_api import (
    get_understat_league_data,
    stessa_squadra,
)


SET_PIECE_SITUATIONS = {
    "FromCorner",
    "SetPiece",
    "DirectFreekick",
}


def _percentage(part, total):
    if total <= 0:
        return None
    return round(100 * part / total, 1)


def _shot_distance_metres(shot):
    """Approximate shot distance from Understat normalized coordinates.

    The conversion assumes a standard 105 x 68 metre pitch and the centre of
    the goal at normalized coordinate (1.0, 0.5). It is descriptive only.
    """
    coordinates = _shot_coordinates(shot)
    if coordinates is None:
        return None

    x, y = coordinates
    longitudinal = (1.0 - x) * 105.0
    lateral = abs(y - 0.5) * 68.0
    return math.hypot(longitudinal, lateral)


def calculate_shot_extras_from_shots(shots, matches_used):
    shots = list(shots or [])
    matches_used = max(0, int(matches_used or 0))

    total_xg = 0.0
    non_penalty_xg = 0.0
    set_piece_xg = 0.0
    goals = 0
    distances = []

    for shot in shots:
        xg = max(0.0, _to_float(shot.get("xG")))
        situation = str(shot.get("situation") or "Unknown")

        total_xg += xg

        if situation != "Penalty":
            non_penalty_xg += xg

        if situation in SET_PIECE_SITUATIONS:
            set_piece_xg += xg

        if shot.get("result") == "Goal":
            goals += 1

        distance = _shot_distance_metres(shot)
        if distance is not None and math.isfinite(distance):
            distances.append(distance)

    return {
        "matches": matches_used,
        "shots": len(shots),
        "goals": goals,
        "xg_total": round(total_xg, 2),
        "non_penalty_xg": round(non_penalty_xg, 2),
        "non_penalty_xg_per_match": _round_or_none(
            None if matches_used <= 0 else non_penalty_xg / matches_used,
            digits=2,
        ),
        "goals_minus_xg": _round_or_none(goals - total_xg, digits=2),
        "set_piece_xg": round(set_piece_xg, 2),
        "set_piece_xg_share_pct": _percentage(set_piece_xg, total_xg),
        "average_shot_distance_m": _round_or_none(
            None if not distances else sum(distances) / len(distances),
            digits=1,
        ),
        "distance_shots": len(distances),
        "set_piece_definition": "FromCorner + SetPiece + DirectFreekick, rigori esclusi",
    }


def _team_recent_shots(league_data, team_name, limit=5):
    team_shots = []
    matches_used = 0

    for match in _recent_finished_team_matches(
        league_data,
        team_name,
        limit=limit,
    ):
        home = (match.get("h") or {}).get("title")
        away = (match.get("a") or {}).get("title")

        try:
            shots = _get_match_shots(match["id"])
        except requests.RequestException:
            continue

        if home and stessa_squadra(team_name, home):
            own_shots = shots["home"]
        elif away and stessa_squadra(team_name, away):
            own_shots = shots["away"]
        else:
            continue

        team_shots.extend(own_shots)
        matches_used += 1

    return team_shots, matches_used


def get_matchup_shot_extras(home_team, away_team, competition, limit=5):
    league_data = get_understat_league_data(competition)

    home_shots, home_matches = _team_recent_shots(
        league_data,
        home_team,
        limit=limit,
    )
    away_shots, away_matches = _team_recent_shots(
        league_data,
        away_team,
        limit=limit,
    )

    return {
        "status": "success",
        "source": "Understat",
        "scope": "ultime_partite",
        "home": calculate_shot_extras_from_shots(home_shots, home_matches),
        "away": calculate_shot_extras_from_shots(away_shots, away_matches),
    }


def get_matchup_shot_extras_safe(home_team, away_team, competition, limit=5):
    try:
        return get_matchup_shot_extras(
            home_team,
            away_team,
            competition,
            limit=limit,
        )
    except (
        requests.RequestException,
        ValueError,
        KeyError,
        TypeError,
    ) as exc:
        return {
            "status": "unavailable",
            "source": "Understat",
            "scope": "ultime_partite",
            "reason": str(exc),
            "home": None,
            "away": None,
        }
