from __future__ import annotations

import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from app.services.football_api import normalizza_nome_squadra


CACHE_SCHEMA_VERSION = 1
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ANALYSIS_CACHE_DIR = Path(
    os.getenv(
        "FOOTBALL_AI_ANALYSIS_CACHE_DIR",
        str(PROJECT_ROOT / "data" / "analysis_cache"),
    )
)
_ANALYSIS_CACHE_LOCK = Lock()


def _season_key(now=None):
    now = now or datetime.now(timezone.utc)
    return now.year if now.month >= 7 else now.year - 1


def _normalize(value):
    return " ".join(str(value or "").strip().lower().split())


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

    return {
        "saved_at": payload.get("saved_at"),
        "response": copy.deepcopy(payload["response"]),
    }


def save_cached_analysis(cache_key, response):
    path = _cache_path(cache_key)
    temp_path = path.with_suffix(".tmp")
    saved_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "cache_key": cache_key,
        "saved_at": saved_at,
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
