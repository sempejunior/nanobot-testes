"""SQLite implementation of CronRepository."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import aiosqlite


def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
    d = dict(row)
    for key in ("schedule", "payload"):
        if key in d and isinstance(d[key], str):
            d[key] = json.loads(d[key])
    return d


class SQLiteCronRepository:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def list_jobs(self, user_id: str, include_disabled: bool = False) -> list[dict[str, Any]]:
        if include_disabled:
            cursor = await self._db.execute(
                "SELECT * FROM cron_jobs WHERE user_id = ? ORDER BY next_run_at_ms ASC NULLS LAST",
                (user_id,),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM cron_jobs WHERE user_id = ? AND enabled = 1 ORDER BY next_run_at_ms ASC NULLS LAST",
                (user_id,),
            )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]

    async def get_job(self, user_id: str, job_id: str) -> dict[str, Any] | None:
        cursor = await self._db.execute(
            "SELECT * FROM cron_jobs WHERE user_id = ? AND job_id = ?", (user_id, job_id),
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None

    async def get_due_jobs(self, now_ms: int) -> list[dict[str, Any]]:
        cursor = await self._db.execute(
            """SELECT * FROM cron_jobs
               WHERE enabled = 1 AND next_run_at_ms IS NOT NULL AND next_run_at_ms <= ?
               ORDER BY next_run_at_ms ASC""",
            (now_ms,),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]

    async def save_job(self, job: dict[str, Any]) -> None:
        now = datetime.now().isoformat()
        schedule = job["schedule"]
        payload = job["payload"]
        if not isinstance(schedule, str):
            schedule = json.dumps(schedule)
        if not isinstance(payload, str):
            payload = json.dumps(payload)

        await self._db.execute(
            """INSERT INTO cron_jobs
               (user_id, job_id, name, enabled, schedule, payload,
                next_run_at_ms, last_run_at_ms, last_status, last_error,
                delete_after_run, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id, job_id)
               DO UPDATE SET
                   name = excluded.name,
                   enabled = excluded.enabled,
                   schedule = excluded.schedule,
                   payload = excluded.payload,
                   next_run_at_ms = excluded.next_run_at_ms,
                   last_run_at_ms = excluded.last_run_at_ms,
                   last_status = excluded.last_status,
                   last_error = excluded.last_error,
                   delete_after_run = excluded.delete_after_run,
                   updated_at = excluded.updated_at""",
            (
                job["user_id"],
                job["job_id"],
                job["name"],
                1 if job.get("enabled", True) else 0,
                schedule,
                payload,
                job.get("next_run_at_ms"),
                job.get("last_run_at_ms"),
                job.get("last_status"),
                job.get("last_error"),
                1 if job.get("delete_after_run") else 0,
                job.get("created_at", now),
                now,
            ),
        )
        await self._db.commit()

    async def delete_job(self, user_id: str, job_id: str) -> bool:
        cursor = await self._db.execute(
            "DELETE FROM cron_jobs WHERE user_id = ? AND job_id = ?", (user_id, job_id),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def update_job_state(self, job_id: str, state: dict[str, Any], *, user_id: str | None = None) -> None:
        sets = []
        values = []
        for key in ("next_run_at_ms", "last_run_at_ms", "last_status", "last_error", "enabled"):
            if key in state:
                sets.append(f"{key} = ?")
                values.append(state[key])
        if not sets:
            return
        sets.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(job_id)

        where = "WHERE job_id = ?"
        if user_id is not None:
            where += " AND user_id = ?"
            values.append(user_id)

        await self._db.execute(
            f"UPDATE cron_jobs SET {', '.join(sets)} {where}", values,
        )
        await self._db.commit()

    async def count_jobs(self, user_id: str) -> int:
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM cron_jobs WHERE user_id = ?", (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
