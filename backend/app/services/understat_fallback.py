from __future__ import annotations

from datetime import datetime, timezone

from app.services.analysis_cache import record_understat_snapshot
from app.services.competitions import DEFAULT_COMPETITION, get_competition_config
from app.services.football_api import get_understat_league_data, stessa_squadra


def _parse_understat_datetime(value):
    if not value:
        return None

    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _goal_number(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if number.is_integer():
        return int(number)
    return number


def build_understat_recent_form_from_league_data(
    league_data,
    team_name,
    competition_name,
    limit=5,
):
    """Normalize recent Understat results to Football AI's recent-form shape.

    Understat does not expose provider-only fields such as corners, cards,
    possession or attacks in league data, so those values remain explicitly
    missing (None) rather than being converted into false zeros.
    """
    rows = []

    for match in league_data.get("dates", []):
        if not match.get("isResult"):
            continue

        home = (match.get("h") or {}).get("title")
        away = (match.get("a") or {}).get("title")
        if not home or not away:
            continue

        is_home = stessa_squadra(team_name, home)
        is_away = stessa_squadra(team_name, away)
        if not is_home and not is_away:
            continue

        goals = match.get("goals") or {}
        home_goals = _goal_number(goals.get("h"))
        away_goals = _goal_number(goals.get("a"))
        if home_goals is None or away_goals is None:
            continue

        if is_home:
            goals_for = home_goals
            goals_against = away_goals
            opponent = away
            context = "casa"
        else:
            goals_for = away_goals
            goals_against = home_goals
            opponent = home
            context = "trasferta"

        dt = _parse_understat_datetime(match.get("datetime"))

        rows.append({
            "data": dt.isoformat() if dt else match.get("datetime"),
            "avversario": opponent,
            "competizione": competition_name,
            "risultato": f"{home_goals}-{away_goals}",
            "gol_fatti": goals_for,
            "gol_subiti": goals_against,
            "corner": None,
            "ammonizioni": None,
            "possesso": None,
            "tiri_in_porta": None,
            "tiri_fuori": None,
            "attacchi": None,
            "attacchi_pericolosi": None,
            "casa_trasferta": context,
            "fonte": "Understat",
            "dati_parziali": True,
        })

    rows.sort(key=lambda item: item.get("data") or "", reverse=True)
    return rows[: max(1, int(limit))]


def get_understat_recent_form(
    team_name,
    competizione=DEFAULT_COMPETITION,
    limit=5,
):
    config = get_competition_config(competizione)
    league_data = get_understat_league_data(config["slug"])
    record_understat_snapshot(config["slug"], league_data)
    return build_understat_recent_form_from_league_data(
        league_data,
        team_name,
        config["name"],
        limit=limit,
    )


def build_understat_upcoming_from_league_data(
    league_data,
    competition_name,
    limit=20,
    now=None,
):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    fixtures = []

    for match in league_data.get("dates", []):
        if match.get("isResult"):
            continue

        home = (match.get("h") or {}).get("title")
        away = (match.get("a") or {}).get("title")
        if not home or not away:
            continue

        kickoff = _parse_understat_datetime(match.get("datetime"))
        if kickoff is None or kickoff <= now:
            continue

        match_id = match.get("id")
        fixtures.append({
            "id": f"understat-{match_id}" if match_id is not None else None,
            "kickoff_ts": kickoff.timestamp(),
            "kickoff_utc": kickoff.isoformat(),
            "status": "scheduled",
            "home": home,
            "away": away,
            "league": competition_name,
            "source": "Understat",
            "data_fallback": True,
        })

    fixtures.sort(key=lambda item: item["kickoff_ts"])
    return fixtures[: max(1, min(int(limit), 50))]


def get_understat_upcoming_fixtures(
    competizione=DEFAULT_COMPETITION,
    limit=20,
):
    config = get_competition_config(competizione)
    league_data = get_understat_league_data(config["slug"])
    record_understat_snapshot(config["slug"], league_data)
    return build_understat_upcoming_from_league_data(
        league_data,
        config["name"],
        limit=limit,
    )
