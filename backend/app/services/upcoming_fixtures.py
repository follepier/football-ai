from __future__ import annotations

from datetime import datetime, timezone

from app.services.competitions import DEFAULT_COMPETITION, get_competition_config
from app.services.football_api import get_league_fixtures


def get_upcoming_fixtures(
    competizione=DEFAULT_COMPETITION,
    limit=20,
):
    """Restituisce le prossime fixture future ordinate per data.

    Usa la lista fixture gia' cache-izzata dal provider e filtra in base al
    timestamp, senza dipendere da una stringa di stato specifica del provider.
    """
    config = get_competition_config(competizione)
    fixtures = get_league_fixtures(config["slug"]).get("data", [])
    now_ts = datetime.now(timezone.utc).timestamp()

    risultati = []
    visti = set()

    for fixture in fixtures:
        kickoff_ts = fixture.get("kickoff_ts")
        try:
            kickoff_ts = float(kickoff_ts)
        except (TypeError, ValueError):
            continue

        if kickoff_ts <= now_ts:
            continue

        teams = fixture.get("teams", {})
        home = teams.get("home", {}).get("name")
        away = teams.get("away", {}).get("name")
        if not home or not away:
            continue

        fixture_id = fixture.get("id")
        dedupe_key = (
            str(fixture_id)
            if fixture_id is not None
            else f"{kickoff_ts}:{home}:{away}"
        )
        if dedupe_key in visti:
            continue
        visti.add(dedupe_key)

        risultati.append({
            "id": fixture_id,
            "kickoff_ts": kickoff_ts,
            "kickoff_utc": fixture.get("kickoff_utc"),
            "status": fixture.get("status"),
            "home": home,
            "away": away,
            "league": fixture.get("league", {}).get("name", config["name"]),
        })

    risultati.sort(key=lambda item: item["kickoff_ts"])

    limite = max(1, min(int(limit), 50))
    return risultati[:limite]
