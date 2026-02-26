"""SQLite implementation of ChannelBindingRepository."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import aiosqlite


class SQLiteChannelBindingRepository:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def resolve_user(self, channel: str, sender_id: str) -> str | None:
        cursor = await self._db.execute(
            "SELECT user_id FROM channel_bindings WHERE channel = ? AND sender_id = ?",
            (channel, sender_id),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def bind(self, user_id: str, channel: str, sender_id: str) -> None:
        now = datetime.now().isoformat()
        await self._db.execute(
            """INSERT INTO channel_bindings (user_id, channel, sender_id, verified, created_at)
               VALUES (?, ?, ?, 1, ?)
               ON CONFLICT(channel, sender_id)
               DO UPDATE SET user_id = excluded.user_id""",
            (user_id, channel, sender_id, now),
        )
        await self._db.commit()

    async def unbind(self, user_id: str, channel: str, sender_id: str) -> bool:
        cursor = await self._db.execute(
            "DELETE FROM channel_bindings WHERE user_id = ? AND channel = ? AND sender_id = ?",
            (user_id, channel, sender_id),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def list_bindings(self, user_id: str) -> list[dict[str, Any]]:
        cursor = await self._db.execute(
            "SELECT * FROM channel_bindings WHERE user_id = ? ORDER BY channel, sender_id",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
