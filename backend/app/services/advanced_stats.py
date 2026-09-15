import math
import time
from threading import Lock

import requests

from app.services.football_api import (
    get_understat_league_data,
    stessa_squadra,
)


UNDERSTAT_MATCH_URL = "https://understat.com/getMatchData/{match_id}"
UNDERSTAT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://understat.com/",
}
MATCH_SHOTS_CACHE_TTL_SECONDS = 3600
_MATCH_SHOTS_CACHE = {}
_MATCH_SHOTS_CACHE_LOCK = Lock()


def _to_float(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(number):
        return default

    return number


def _round_or_none(value, digits=2):
    if value is None:
        return None
    return round(float(value), digits)


def _team_records(league_data):
    teams = league_data.get("teams", {})

    if isinstance(teams, dict):
        return list(teams.values())

    if isinstance(teams, list):
        return teams

    return []


def _find_team_record(league_data, team_name):
    for team in _team_records(league_data):
        title = team.get("title") or team.get("name")
        if title and stessa_squadra(title, team_name):
            return team

    raise ValueError(f"Squadra non trovata nei dati Understat: {team_name}")


def _players_for_team(league_data, team_name):
    players = league_data.get("players", [])
    if not isinstance(players, list):
        return []

    return [
        player
        for player in players
        if player.get("team_title")
        and stessa_squadra(player.get("team_title"), team_name)
    ]


def _shot_coordinates(shot):
    try:
        x = float(shot.get("X"))
        y = float(shot.get("Y"))
    except (TypeError, ValueError):
        return None

    if not math.isfinite(x) or not math.isfinite(y):
        return None

    if x < 0 or x > 1 or y < 0 or y > 1:
        return None

    return x, y


def is_inside_penalty_area(shot):
    """Return True when an Understat shot is inside the penalty area.

    Understat uses normalized pitch coordinates: X grows toward the goal and
    Y spans the pitch width. The thresholds below approximate the standard
    penalty-area rectangle on that normalized pitch.
    """
    coordinates = _shot_coordinates(shot)
    if coordinates is None:
        return False

    x, y = coordinates
    return x >= 0.833 and 0.211 <= y <= 0.789


def saved_shots_inside_box(shots):
    return sum(
        1
        for shot in shots
        if shot.get("result") == "SavedShot"
        and is_inside_penalty_area(shot)
    )


def build_shot_heatmap(shots, columns=8, rows=6):
    """Build a compact xG-weighted shot heatmap from Understat coordinates."""
    columns = max(2, int(columns))
    rows = max(2, int(rows))
    bins = [
        [
            {"shots": 0, "xg": 0.0}
            for _ in range(columns)
        ]
        for _ in range(rows)
    ]

    valid_shots = 0
    total_xg = 0.0

    for shot in shots or []:
        coordinates = _shot_coordinates(shot)
        if coordinates is None:
            continue

        x, y = coordinates
        column = min(columns - 1, int(x * columns))
        row = min(rows - 1, int(y * rows))
        xg = max(0.0, _to_float(shot.get("xG")))

        bins[row][column]["shots"] += 1
        bins[row][column]["xg"] += xg
        valid_shots += 1
        total_xg += xg

    max_bin_xg = max(
        (cell["xg"] for row in bins for cell in row),
        default=0.0,
    )
    max_bin_shots = max(
        (cell["shots"] for row in bins for cell in row),
        default=0,
    )

    cells = []
    for row_index, row_values in enumerate(bins):
        for column_index, cell in enumerate(row_values):
            if max_bin_xg > 0:
                intensity = cell["xg"] / max_bin_xg
            elif max_bin_shots > 0:
                intensity = cell["shots"] / max_bin_shots
            else:
                intensity = 0.0

            cells.append(
                {
                    "row": row_index,
                    "column": column_index,
                    "shots": cell["shots"],
                    "xg": round(cell["xg"], 3),
                    "intensity": round(intensity, 3),
                }
            )

    return {
        "columns": columns,
        "rows": rows,
        "shots": valid_shots,
        "xg_total": round(total_xg, 2),
        "xg_per_shot": _round_or_none(
            None if valid_shots <= 0 else total_xg / valid_shots,
            digits=3,
        ),
        "cells": cells,
    }


def _get_match_shots(match_id):
    cache_key = str(match_id)
    now = time.monotonic()

    with _MATCH_SHOTS_CACHE_LOCK:
        cached = _MATCH_SHOTS_CACHE.get(cache_key)
        if cached is not None and now < cached["expires_at"]:
            return cached["value"]

    response = requests.get(
        UNDERSTAT_MATCH_URL.format(match_id=match_id),
        headers=UNDERSTAT_HEADERS,
        timeout=15,
    )
    response.raise_for_status()

    payload = response.json()
    shots = payload.get("shots", {})
    result = {
        "home": shots.get("h", []),
        "away": shots.get("a", []),
    }

    with _MATCH_SHOTS_CACHE_LOCK:
        _MATCH_SHOTS_CACHE[cache_key] = {
            "expires_at": time.monotonic() + MATCH_SHOTS_CACHE_TTL_SECONDS,
            "value": result,
        }

    return result


def _recent_finished_team_matches(league_data, team_name, limit=5):
    matches = []

    for row in league_data.get("dates", []):
        if not row.get("isResult") or not row.get("id"):
            continue

        home = (row.get("h") or {}).get("title")
        away = (row.get("a") or {}).get("title")

        if not home or not away:
            continue

        if stessa_squadra(team_name, home) or stessa_squadra(team_name, away):
            matches.append(row)

    matches.sort(key=lambda row: row.get("datetime", ""), reverse=True)
    return matches[: max(1, int(limit))]


def calculate_recent_saves_inside_box(
    league_data,
    team_name,
    limit=5,
):
    """Average goalkeeper saves on shots from inside the box.

    The metric is intentionally recent rather than season-wide to avoid dozens
    of Understat match-data requests per analysis. Match shot data is cached.
    Failed optional Understat match requests are skipped instead of invalidating
    the main Football AI analysis.
    """
    samples = []

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
            faced_shots = shots["away"]
        elif away and stessa_squadra(team_name, away):
            faced_shots = shots["home"]
        else:
            continue

        samples.append(saved_shots_inside_box(faced_shots))

    if not samples:
        return {
            "saves_inside_box_per_match": None,
            "saves_inside_box_matches": 0,
        }

    return {
        "saves_inside_box_per_match": _round_or_none(
            sum(samples) / len(samples)
        ),
        "saves_inside_box_matches": len(samples),
    }


def calculate_recent_shot_heatmap(
    league_data,
    team_name,
    limit=5,
):
    """Build the team's recent offensive shot map from real Understat shots."""
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

    heatmap = build_shot_heatmap(team_shots)
    heatmap["matches"] = matches_used
    heatmap["source"] = "Understat"
    heatmap["scope"] = "ultime_partite"
    return heatmap


def calculate_team_advanced_metrics_from_league_data(
    league_data,
    team_name,
):
    team = _find_team_record(league_data, team_name)
    history = team.get("history", [])

    if not isinstance(history, list):
        history = []

    matches = len(history)

    ppda_att = sum(
        _to_float((row.get("ppda") or {}).get("att"))
        for row in history
    )
    ppda_def = sum(
        _to_float((row.get("ppda") or {}).get("def"))
        for row in history
    )
    ppda = None if ppda_def <= 0 else ppda_att / ppda_def

    deep = sum(_to_float(row.get("deep")) for row in history)
    deep_allowed = sum(
        _to_float(row.get("deep_allowed"))
        for row in history
    )

    territorial_total = deep + deep_allowed
    field_tilt_proxy = (
        None
        if territorial_total <= 0
        else (deep / territorial_total) * 100
    )

    players = _players_for_team(league_data, team_name)
    expected_assists_total = sum(
        _to_float(player.get("xA"))
        for player in players
    )
    key_passes_total = sum(
        _to_float(player.get("key_passes"))
        for player in players
    )

    per_match_denominator = matches if matches > 0 else None

    return {
        "team": team.get("title") or team_name,
        "source": "Understat",
        "scope": "stagione_corrente",
        "matches": matches,
        "ppda": _round_or_none(ppda),
        "expected_assists_per_match": _round_or_none(
            None
            if per_match_denominator is None
            else expected_assists_total / per_match_denominator
        ),
        "key_passes_per_match": _round_or_none(
            None
            if per_match_denominator is None
            else key_passes_total / per_match_denominator
        ),
        "deep_completions_per_match": _round_or_none(
            None
            if per_match_denominator is None
            else deep / per_match_denominator
        ),
        "deep_allowed_per_match": _round_or_none(
            None
            if per_match_denominator is None
            else deep_allowed / per_match_denominator
        ),
        "field_tilt_proxy": _round_or_none(field_tilt_proxy),
        "field_tilt_status": "proxy_published",
    }


def _with_recent_spatial_metrics(league_data, team_name, metrics):
    return {
        **metrics,
        **calculate_recent_saves_inside_box(
            league_data,
            team_name,
            limit=5,
        ),
        "shot_heatmap": calculate_recent_shot_heatmap(
            league_data,
            team_name,
            limit=5,
        ),
    }


def get_matchup_advanced_metrics(
    home_team,
    away_team,
    competition,
):
    league_data = get_understat_league_data(competition)

    home_metrics = calculate_team_advanced_metrics_from_league_data(
        league_data,
        home_team,
    )
    away_metrics = calculate_team_advanced_metrics_from_league_data(
        league_data,
        away_team,
    )

    return {
        "status": "success",
        "source": "Understat",
        "scope": "stagione_corrente",
        "home": _with_recent_spatial_metrics(
            league_data,
            home_team,
            home_metrics,
        ),
        "away": _with_recent_spatial_metrics(
            league_data,
            away_team,
            away_metrics,
        ),
        "experimental": {
            "field_tilt_proxy": True,
            "saves_inside_box": "derived_recent_published",
            "shot_heatmap": "derived_recent_published",
        },
    }


def get_matchup_advanced_metrics_safe(
    home_team,
    away_team,
    competition,
):
    try:
        return get_matchup_advanced_metrics(
            home_team,
            away_team,
            competition,
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
            "scope": "stagione_corrente",
            "reason": str(exc),
            "home": None,
            "away": None,
            "experimental": {
                "field_tilt_proxy": True,
                "saves_inside_box": "derived_recent_published",
                "shot_heatmap": "derived_recent_published",
            },
        }
