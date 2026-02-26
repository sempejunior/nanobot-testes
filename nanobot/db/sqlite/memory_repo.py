"""SQLite implementation of MemoryRepository."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import aiosqlite


class SQLiteMemoryRepository:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def get_long_term(self, user_id: str) -> str:
        cursor = await self._db.execute(
            "SELECT content FROM memories WHERE user_id = ? AND type = 'long_term' LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else ""

    async def save_long_term(self, user_id: str, content: str) -> None:
        now = datetime.now().isoformat()
        cursor = await self._db.execute(
            "SELECT id FROM memories WHERE user_id = ? AND type = 'long_term' LIMIT 1",
            (user_id,),
        )
        existing = await cursor.fetchone()

        if existing:
            await self._db.execute(
                "UPDATE memories SET content = ?, updated_at = ? WHERE id = ?",
                (content, now, existing[0]),
            )
        else:
            await self._db.execute(
                "INSERT INTO memories (user_id, type, content, created_at, updated_at) VALUES (?, 'long_term', ?, ?, ?)",
                (user_id, content, now, now),
            )
        await self._db.commit()

    async def append_history(self, user_id: str, entry: str) -> None:
        now = datetime.now().isoformat()
        await self._db.execute(
            "INSERT INTO memories (user_id, type, content, created_at, updated_at) VALUES (?, 'history', ?, ?, ?)",
            (user_id, entry.rstrip(), now, now),
        )
        await self._db.commit()

    async def get_history(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        cursor = await self._db.execute(
            """SELECT id, content, created_at FROM memories
               WHERE user_id = ? AND type = 'history'
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def search_history(self, user_id: str, query: str, limit: int = 50) -> list[dict[str, Any]]:
        try:
            cursor = await self._db.execute(
                """SELECT m.id, m.content, m.created_at, fts.rank AS relevance
                   FROM memories_fts fts
                   JOIN memories m ON m.id = fts.rowid
                   WHERE memories_fts MATCH ?
                     AND m.user_id = ? AND m.type = 'history'
                   ORDER BY fts.rank LIMIT ?""",
                (query, user_id, limit),
            )
            return [dict(r) for r in await cursor.fetchall()]
        except Exception:
            pattern = f"%{query}%"
            cursor = await self._db.execute(
                """SELECT id, content, created_at FROM memories
                   WHERE user_id = ? AND type = 'history' AND content LIKE ?
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, pattern, limit),
            )
            return [dict(r) for r in await cursor.fetchall()]

    async def delete_history(self, user_id: str, entry_id: int) -> bool:
        cursor = await self._db.execute(
            "DELETE FROM memories WHERE user_id = ? AND id = ? AND type = 'history'",
            (user_id, entry_id),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def clear_history(self, user_id: str) -> int:
        cursor = await self._db.execute(
            "DELETE FROM memories WHERE user_id = ? AND type = 'history'",
            (user_id,),
        )
        await self._db.commit()
        return cursor.rowcount
