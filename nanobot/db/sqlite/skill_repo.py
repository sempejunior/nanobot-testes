"""SQLite implementation of SkillRepository."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import aiosqlite


class SQLiteSkillRepository:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def list_skills(self, user_id: str, enabled_only: bool = True) -> list[dict[str, Any]]:
        if enabled_only:
            cursor = await self._db.execute(
                "SELECT * FROM skills WHERE user_id = ? AND enabled = 1 ORDER BY name",
                (user_id,),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM skills WHERE user_id = ? ORDER BY name", (user_id,),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_skill(self, user_id: str, name: str) -> dict[str, Any] | None:
        cursor = await self._db.execute(
            "SELECT * FROM skills WHERE user_id = ? AND name = ?", (user_id, name),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def save_skill(self, user_id: str, skill: dict[str, Any]) -> None:
        now = datetime.now().isoformat()
        await self._db.execute(
            """INSERT INTO skills (user_id, name, content, description, always_active, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id, name)
               DO UPDATE SET
                   content = excluded.content,
                   description = excluded.description,
                   always_active = excluded.always_active,
                   enabled = excluded.enabled,
                   updated_at = excluded.updated_at""",
            (
                user_id,
                skill["name"],
                skill["content"],
                skill.get("description", ""),
                1 if skill.get("always_active") else 0,
                1 if skill.get("enabled", True) else 0,
                now,
                now,
            ),
        )
        await self._db.commit()

    async def delete_skill(self, user_id: str, name: str) -> bool:
        cursor = await self._db.execute(
            "DELETE FROM skills WHERE user_id = ? AND name = ?", (user_id, name),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def count_skills(self, user_id: str) -> int:
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM skills WHERE user_id = ?", (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
