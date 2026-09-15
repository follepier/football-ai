from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from threading import Lock

import psycopg
from psycopg.types.json import Jsonb


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
_STATE_TABLE = "football_ai_state"
_INIT_LOCK = Lock()
_INITIALIZED = False


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def _connect():
    return psycopg.connect(DATABASE_URL, autocommit=True)


def _ensure_table():
    global _INITIALIZED

    if not DATABASE_URL:
        return False
    if _INITIALIZED:
        return True

    with _INIT_LOCK:
        if _INITIALIZED:
            return True

        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {_STATE_TABLE} (
                        state_key TEXT PRIMARY KEY,
                        payload JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )

        _INITIALIZED = True
        return True


def _db_get(state_key):
    if not _ensure_table():
        return None

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT payload FROM {_STATE_TABLE} WHERE state_key = %s",
                (state_key,),
            )
            row = cur.fetchone()

    if not row:
        return None

    payload = row[0]
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            return None

    return copy.deepcopy(payload) if isinstance(payload, dict) else None


def _db_put(state_key, payload):
    if not _ensure_table():
        return False

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {_STATE_TABLE} (state_key, payload, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (state_key)
                DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()
                """,
                (state_key, Jsonb(payload)),
            )

    return True


def install_database_storage():
    """Use PostgreSQL/Neon for shared cache state when DATABASE_URL is set.

    Local development keeps the existing filesystem implementation. In hosted
    environments, the public web service can share the same saved analyses and
    freshness index across users and server restarts.
    """
    if not DATABASE_URL:
        return False

    from app.services import analysis_cache

    freshness_key = "freshness:v1"

    def load_freshness_unlocked():
        try:
            payload = _db_get(freshness_key)
        except (psycopg.Error, OSError, ValueError, TypeError):
            payload = None

        if not isinstance(payload, dict):
            return {"version": 1, "competitions": {}}

        payload.setdefault("version", 1)
        payload.setdefault("competitions", {})
        return payload

    def save_freshness_unlocked(payload):
        try:
            _db_put(freshness_key, payload)
        except (psycopg.Error, OSError, ValueError, TypeError):
            return None
        return True

    def load_cached_analysis(cache_key):
        try:
            payload = _db_get(f"analysis:{cache_key}")
        except (psycopg.Error, OSError, ValueError, TypeError):
            return None

        if not isinstance(payload, dict):
            return None
        if payload.get("schema_version") != analysis_cache.CACHE_SCHEMA_VERSION:
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
        saved_at = saved_at or _utc_now_iso()
        payload = {
            "schema_version": analysis_cache.CACHE_SCHEMA_VERSION,
            "cache_key": cache_key,
            "saved_at": saved_at,
            "metadata": metadata or {},
            "response": response,
        }

        try:
            if not _db_put(f"analysis:{cache_key}", payload):
                return None
        except (psycopg.Error, OSError, ValueError, TypeError):
            return None

        return saved_at

    analysis_cache._load_freshness_unlocked = load_freshness_unlocked
    analysis_cache._save_freshness_unlocked = save_freshness_unlocked
    analysis_cache.load_cached_analysis = load_cached_analysis
    analysis_cache.save_cached_analysis = save_cached_analysis

    return True
