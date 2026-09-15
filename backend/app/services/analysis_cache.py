from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from threading import Lock

from app.services.football_api import normalizza_nome_squadra


CACHE_SCHEMA_VERSION = 2
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ANALYSIS_CACHE_DIR = Path(
    os.getenv(
        "FOOTBALL_AI_ANALYSIS_CACHE_DIR",
        str(PROJECT_ROOT / "data" / "analysis_cache"),
    )
)
_ANALYSIS_CACHE_LOCK = Lock()
_ANALYSIS_COMPUTE_LOCKS_GUARD = Lock()
_ANALYSIS_COMPUTE_LOCKS = {}


def _season_key(now=None):
    now = now or datetime.now(timezone.utc)
    return now.year if now.month >= 7 else now.year - 1


def _normalize(value):
    return " ".join(str(value or "").strip().lower().split())


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def _to_timestamp(value):
    if value is None or value == "":
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        pass

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).timestamp()


def build_analysis_cache_key(competition, home_team, away_team, season=None):
    season = int(season if season is not None else _season_key())
    raw = "|".join(
        [
            str(CACHE_SCHEMA_VERSION),
            str(season),
            _normalize(competition),
            normalizza_nome_squadra(home_team),
            normalizza_nome_squadra(away_team),
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"v{CACHE_SCHEMA_VERSION}_{season}_{digest}"


def _cache_path(cache_key):
    ANALYSIS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return ANALYSIS_CACHE_DIR / f"{cache_key}.json"


def _freshness_path():
    ANALYSIS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return ANALYSIS_CACHE_DIR / "_freshness.json"


def _load_freshness_unlocked():
    try:
        with _freshness_path().open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        return {"version": 1, "competitions": {}}

    if not isinstance(payload, dict):
        return {"version": 1, "competitions": {}}

    payload.setdefault("version", 1)
    payload.setdefault("competitions", {})
    return payload


def _save_freshness_unlocked(payload):
    path = _freshness_path()
    temp_path = path.with_suffix(".tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        os.replace(temp_path, path)
    except OSError:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass


def _update_freshness_index(
    competition,
    team_latest_finished,
    *,
    source,
    provider_success=False,
    observed_at=None,
):
    observed_at = observed_at or _utc_now_iso()
    observed_ts = _to_timestamp(observed_at)
    if observed_ts is None:
        observed_ts = datetime.now(timezone.utc).timestamp()
        observed_at = datetime.fromtimestamp(observed_ts, timezone.utc).isoformat()

    competition_key = _normalize(competition)

    with _ANALYSIS_CACHE_LOCK:
        payload = _load_freshness_unlocked()
        competitions = payload.setdefault("competitions", {})
        competition_data = competitions.setdefault(
            competition_key,
            {"teams": {}},
        )
        teams = competition_data.setdefault("teams", {})

        for team_name, latest_ts in team_latest_finished.items():
            latest_ts = _to_timestamp(latest_ts)
            if latest_ts is None:
                continue

            team_key = normalizza_nome_squadra(team_name)
            current = teams.get(team_key) or {}
            current_ts = _to_timestamp(current.get("latest_finished_ts"))

            if current_ts is None or latest_ts > current_ts:
                teams[team_key] = {
                    "latest_finished_ts": latest_ts,
                    "source": source,
                    "observed_at": observed_at,
                }

        competition_data["last_snapshot_at"] = observed_at
        if provider_success:
            competition_data["provider_last_success_at"] = observed_at
            competition_data["provider_last_success_ts"] = observed_ts

        _save_freshness_unlocked(payload)


def record_provider_fixture_snapshot(competition, fixtures, observed_at=None):
    """Registra solo dati gia' caricati dal provider; non effettua chiamate HTTP."""
    latest = {}

    for fixture in fixtures or []:
        if fixture.get("status") != "finished":
            continue

        kickoff_ts = _to_timestamp(fixture.get("kickoff_ts"))
        teams = fixture.get("teams") or {}
        home = (teams.get("home") or {}).get("name")
        away = (teams.get("away") or {}).get("name")
        if kickoff_ts is None or not home or not away:
            continue

        for team in (home, away):
            previous = latest.get(team)
            if previous is None or kickoff_ts > previous:
                latest[team] = kickoff_ts

    _update_freshness_index(
        competition,
        latest,
        source="5DollarFootballAPI",
        provider_success=True,
        observed_at=observed_at,
    )


def record_understat_snapshot(competition, league_data, observed_at=None):
    """Registra i risultati Understat appena acquisiti senza nuove richieste."""
    latest = {}

    for match in (league_data or {}).get("dates", []):
        if not match.get("isResult"):
            continue

        kickoff_ts = _to_timestamp(match.get("datetime"))
        home = (match.get("h") or {}).get("title")
        away = (match.get("a") or {}).get("title")
        if kickoff_ts is None or not home or not away:
            continue

        for team in (home, away):
            previous = latest.get(team)
            if previous is None or kickoff_ts > previous:
                latest[team] = kickoff_ts

    _update_freshness_index(
        competition,
        latest,
        source="Understat",
        provider_success=False,
        observed_at=observed_at,
    )


def get_freshness_snapshot(competition, home_team, away_team):
    competition_key = _normalize(competition)
    home_key = normalizza_nome_squadra(home_team)
    away_key = normalizza_nome_squadra(away_team)

    with _ANALYSIS_CACHE_LOCK:
        payload = _load_freshness_unlocked()

    competition_data = (payload.get("competitions") or {}).get(
        competition_key,
        {},
    )
    teams = competition_data.get("teams") or {}

    def latest(team_key):
        return _to_timestamp((teams.get(team_key) or {}).get("latest_finished_ts"))

    return {
        "home_latest_finished_ts": latest(home_key),
        "away_latest_finished_ts": latest(away_key),
        "provider_last_success_ts": _to_timestamp(
            competition_data.get("provider_last_success_ts")
            or competition_data.get("provider_last_success_at")
        ),
        "last_snapshot_at": competition_data.get("last_snapshot_at"),
    }


def load_cached_analysis(cache_key):
    path = _cache_path(cache_key)

    with _ANALYSIS_CACHE_LOCK:
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError, TypeError):
            return None

    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != CACHE_SCHEMA_VERSION:
        return None
    if payload.get("cache_key") != cache_key:
        return None
    if not isinstance(payload.get("response"), dict):
        return None

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    return {
        "saved_at": payload.get("saved_at"),
        "metadata": copy.deepcopy(metadata),
        "response": copy.deepcopy(payload["response"]),
    }


def save_cached_analysis(
    cache_key,
    response,
    *,
    metadata=None,
    saved_at=None,
):
    path = _cache_path(cache_key)
    temp_path = path.with_suffix(".tmp")
    saved_at = saved_at or _utc_now_iso()
    payload = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "cache_key": cache_key,
        "saved_at": saved_at,
        "metadata": metadata or {},
        "response": response,
    }

    with _ANALYSIS_CACHE_LOCK:
        try:
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            os.replace(temp_path, path)
        except (OSError, TypeError, ValueError):
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
            return None

    return saved_at


def evaluate_cached_analysis(
    cached,
    competition,
    home_team,
    away_team,
    *,
    kickoff_ts=None,
    now_ts=None,
):
    """Decide se una copia salvata e' ancora valida usando solo dati locali.

    Nessuna fonte esterna viene interrogata qui: la freshness viene aggiornata
    soltanto quando Football AI ha gia' caricato un nuovo snapshot delle fonti.
    """
    metadata = cached.get("metadata") or {}
    effective_kickoff = _to_timestamp(
        kickoff_ts if kickoff_ts is not None else metadata.get("kickoff_ts")
    )
    now_ts = float(
        now_ts
        if now_ts is not None
        else datetime.now(timezone.utc).timestamp()
    )

    if effective_kickoff is not None and now_ts >= effective_kickoff:
        return {
            "valid": True,
            "frozen": True,
            "reason": None,
        }

    current = get_freshness_snapshot(
        competition,
        home_team,
        away_team,
    )
    stored = metadata.get("freshness") or {}

    for side in ("home", "away"):
        current_ts = _to_timestamp(current.get(f"{side}_latest_finished_ts"))
        stored_ts = _to_timestamp(stored.get(f"{side}_latest_finished_ts"))
        if current_ts is not None and (
            stored_ts is None or current_ts > stored_ts + 0.5
        ):
            return {
                "valid": False,
                "frozen": False,
                "reason": "new_finished_match",
            }

    if metadata.get("provisional"):
        provider_success_ts = _to_timestamp(current.get("provider_last_success_ts"))
        saved_ts = _to_timestamp(cached.get("saved_at"))
        if (
            provider_success_ts is not None
            and saved_ts is not None
            and provider_success_ts > saved_ts + 0.5
        ):
            return {
                "valid": False,
                "frozen": False,
                "reason": "provider_recovered",
            }

    return {
        "valid": True,
        "frozen": False,
        "reason": None,
    }


def _compute_lock(cache_key):
    with _ANALYSIS_COMPUTE_LOCKS_GUARD:
        lock = _ANALYSIS_COMPUTE_LOCKS.get(cache_key)
        if lock is None:
            lock = Lock()
            _ANALYSIS_COMPUTE_LOCKS[cache_key] = lock
        return lock


def serialize_analysis_requests(func):
    """Evita che utenti simultanei ricalcolino la stessa partita due volte."""
    signature = inspect.signature(func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        bound = signature.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        cache_key = build_analysis_cache_key(
            bound.arguments.get("competizione"),
            bound.arguments.get("casa"),
            bound.arguments.get("ospite"),
        )
        with _compute_lock(cache_key):
            return func(*args, **kwargs)

    return wrapper
