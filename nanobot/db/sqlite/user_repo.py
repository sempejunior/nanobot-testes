"""SQLite implementation of UserRepository."""

from __future__ import annotations

import json
from datetime import datetime, date
from typing import Any

import aiosqlite


_DEFAULT_AGENT_CONFIG = {
    "model": "anthropic/claude-sonnet-4-20250514",
    "max_tokens": 8192,
    "temperature": 0.1,
    "max_tool_iterations": 40,
    "memory_window": 100,
}

_DEFAULT_LIMITS = {
    "max_sessions": 100,
    "max_memory_entries": 10000,
    "max_skills": 50,
    "max_cron_jobs": 20,
    "max_exec_timeout_s": 30,
    "max_tokens_per_day": 1_000_000,
    "max_requests_per_minute": 30,
    "sandbox_memory": "256m",
    "sandbox_cpu": "0.5",
}

_DEFAULT_TOOLS = [
    "web_search", "web_fetch", "exec", "read_file",
    "write_file", "edit_file", "list_dir", "spawn", "cron", "message", "save_skill",
    "save_memory", "search_memory",
]


def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
    d = dict(row)
    for key in ("agent_config", "bootstrap", "limits", "tools_enabled"):
        if key in d and isinstance(d[key], str):
            d[key] = json.loads(d[key])
    return d


class SQLiteUserRepository:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        cursor = await self._db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None

    async def get_by_api_key_hash(self, key_hash: str) -> dict[str, Any] | None:
        cursor = await self._db.execute(
            "SELECT * FROM users WHERE api_key_hash = ?", (key_hash,)
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None

    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        cursor = await self._db.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None

    async def create(self, user: dict[str, Any]) -> str:
        user_id = user["user_id"]
        now = datetime.now().isoformat()
        await self._db.execute(
            """INSERT INTO users
               (user_id, display_name, email, api_key_hash, role,
                agent_config, bootstrap, limits, tools_enabled,
                status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                user.get("display_name", ""),
                user.get("email"),
                user.get("api_key_hash"),
                user.get("role", "user"),
                json.dumps(user.get("agent_config", _DEFAULT_AGENT_CONFIG)),
                json.dumps(user.get("bootstrap", {})),
                json.dumps(user.get("limits", _DEFAULT_LIMITS)),
                json.dumps(user.get("tools_enabled", _DEFAULT_TOOLS)),
                user.get("status", "active"),
                now,
                now,
            ),
        )
        await self._db.commit()
        return user_id

    _ALLOWED_UPDATE_FIELDS = frozenset({
        "display_name", "email", "api_key_hash", "role",
        "agent_config", "bootstrap", "limits", "tools_enabled",
        "status", "updated_at",
        "tokens_today", "requests_today", "tokens_total",
        "usage_reset_date", "last_request_at",
    })

    async def update(self, user_id: str, fields: dict[str, Any]) -> bool:
        if not fields:
            return False

        bad_fields = set(fields) - self._ALLOWED_UPDATE_FIELDS - {"updated_at"}
        if bad_fields:
            raise ValueError(f"Disallowed fields: {bad_fields}")

        for key in ("agent_config", "bootstrap", "limits", "tools_enabled"):
            if key in fields and not isinstance(fields[key], str):
                fields[key] = json.dumps(fields[key])

        fields["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [user_id]

        cursor = await self._db.execute(
            f"UPDATE users SET {set_clause} WHERE user_id = ?", values
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def list_all(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            cursor = await self._db.execute(
                "SELECT * FROM users WHERE status = ? ORDER BY created_at DESC", (status,)
            )
        else:
            cursor = await self._db.execute("SELECT * FROM users ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]

    async def increment_usage(self, user_id: str, tokens: int, requests: int = 1) -> None:
        today = date.today().isoformat()
        now = datetime.now().isoformat()
        await self._db.execute(
            """UPDATE users SET
                tokens_today = CASE WHEN usage_reset_date != ? THEN ? ELSE tokens_today + ? END,
                requests_today = CASE WHEN usage_reset_date != ? THEN ? ELSE requests_today + ? END,
                tokens_total = tokens_total + ?,
                usage_reset_date = ?,
                last_request_at = ?,
                updated_at = ?
               WHERE user_id = ?""",
            (today, tokens, tokens, today, requests, requests, tokens, today, now, now, user_id),
        )
        await self._db.commit()

    async def reset_daily_usage(self) -> int:
        today = date.today().isoformat()
        cursor = await self._db.execute(
            """UPDATE users SET tokens_today = 0, requests_today = 0,
               usage_reset_date = ?, updated_at = ?
               WHERE tokens_today > 0 OR requests_today > 0""",
            (today, datetime.now().isoformat()),
        )
        await self._db.commit()
        return cursor.rowcount
