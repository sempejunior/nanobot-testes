"""SQLite implementation of AuditRepository."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import aiosqlite


class SQLiteAuditRepository:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def log(
        self,
        user_id: str,
        event: str,
        detail: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        await self._db.execute(
            """INSERT INTO audit_log (user_id, event, detail, ip_address, user_agent, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                event,
                json.dumps(detail or {}),
                ip_address,
                user_agent,
                datetime.now().isoformat(),
            ),
        )
        await self._db.commit()

    async def query(
        self,
        *,
        user_id: str | None = None,
        event: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if event:
            conditions.append("event = ?")
            params.append(event)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])

        cursor = await self._db.execute(
            f"""SELECT * FROM audit_log {where}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?""",
            params,
        )
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if isinstance(d.get("detail"), str):
                d["detail"] = json.loads(d["detail"])
            result.append(d)
        return result

    async def cleanup(self, days: int = 90) -> int:
        cursor = await self._db.execute(
            "DELETE FROM audit_log WHERE timestamp < datetime('now', ?)",
            (f"-{days} days",),
        )
        await self._db.commit()
        return cursor.rowcount
