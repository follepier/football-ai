import math

import requests

from app.services.football_api import (
    get_understat_league_data,
    stessa_squadra,
)


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
        "field_tilt_status": "proxy_in_audit",
    }


def get_matchup_advanced_metrics(
    home_team,
    away_team,
    competition,
):
    league_data = get_understat_league_data(competition)

    return {
        "status": "success",
        "source": "Understat",
        "scope": "stagione_corrente",
        "home": calculate_team_advanced_metrics_from_league_data(
            league_data,
            home_team,
        ),
        "away": calculate_team_advanced_metrics_from_league_data(
            league_data,
            away_team,
        ),
        "experimental": {
            "field_tilt_proxy": True,
            "saves_inside_box": "audit_in_corso",
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
                "saves_inside_box": "audit_in_corso",
            },
        }
