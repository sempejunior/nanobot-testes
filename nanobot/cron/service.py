"""Cron service for scheduling agent tasks."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from loguru import logger

from nanobot.cron.types import CronJob, CronJobState, CronPayload, CronSchedule, CronStore

if TYPE_CHECKING:
    from nanobot.db.sqlite.cron_repo import SQLiteCronRepository


def _now_ms() -> int:
    return int(time.time() * 1000)


def _compute_next_run(schedule: CronSchedule, now_ms: int) -> int | None:
    """Compute next run time in ms."""
    if schedule.kind == "at":
        return schedule.at_ms if schedule.at_ms and schedule.at_ms > now_ms else None

    if schedule.kind == "every":
        if not schedule.every_ms or schedule.every_ms <= 0:
            return None
        return now_ms + schedule.every_ms

    if schedule.kind == "cron" and schedule.expr:
        try:
            from croniter import croniter
            from zoneinfo import ZoneInfo
            base_time = now_ms / 1000
            tz = ZoneInfo(schedule.tz) if schedule.tz else datetime.now().astimezone().tzinfo
            base_dt = datetime.fromtimestamp(base_time, tz=tz)
            cron = croniter(schedule.expr, base_dt)
            next_dt = cron.get_next(datetime)
            return int(next_dt.timestamp() * 1000)
        except Exception:
            return None

    return None


def _validate_schedule_for_add(schedule: CronSchedule) -> None:
    """Validate schedule fields that would otherwise create non-runnable jobs."""
    if schedule.tz and schedule.kind != "cron":
        raise ValueError("tz can only be used with cron schedules")

    if schedule.kind == "cron" and schedule.tz:
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(schedule.tz)
        except Exception:
            raise ValueError(f"unknown timezone '{schedule.tz}'") from None


def _job_to_dict(job: CronJob) -> dict[str, Any]:
    """Convert a CronJob to a dict suitable for CronRepository.save_job()."""
    return {
        "user_id": job.user_id,
        "job_id": job.id,
        "name": job.name,
        "enabled": job.enabled,
        "schedule": {
            "kind": job.schedule.kind,
            "at_ms": job.schedule.at_ms,
            "every_ms": job.schedule.every_ms,
            "expr": job.schedule.expr,
            "tz": job.schedule.tz,
        },
        "payload": {
            "kind": job.payload.kind,
            "message": job.payload.message,
            "deliver": job.payload.deliver,
            "channel": job.payload.channel,
            "to": job.payload.to,
        },
        "next_run_at_ms": job.state.next_run_at_ms,
        "last_run_at_ms": job.state.last_run_at_ms,
        "last_status": job.state.last_status,
        "last_error": job.state.last_error,
        "delete_after_run": job.delete_after_run,
    }


def _dict_to_job(d: dict[str, Any]) -> CronJob:
    """Convert a repository dict back to a CronJob."""
    sched = d.get("schedule", {})
    pay = d.get("payload", {})
    return CronJob(
        id=d["job_id"],
        name=d["name"],
        user_id=d.get("user_id", ""),
        enabled=bool(d.get("enabled", True)),
        schedule=CronSchedule(
            kind=sched.get("kind", "every"),
            at_ms=sched.get("at_ms") or sched.get("atMs"),
            every_ms=sched.get("every_ms") or sched.get("everyMs"),
            expr=sched.get("expr"),
            tz=sched.get("tz"),
        ),
        payload=CronPayload(
            kind=pay.get("kind", "agent_turn"),
            message=pay.get("message", ""),
            deliver=pay.get("deliver", False),
            channel=pay.get("channel"),
            to=pay.get("to"),
        ),
        state=CronJobState(
            next_run_at_ms=d.get("next_run_at_ms"),
            last_run_at_ms=d.get("last_run_at_ms"),
            last_status=d.get("last_status"),
            last_error=d.get("last_error"),
        ),
        created_at_ms=d.get("created_at_ms", 0),
        updated_at_ms=d.get("updated_at_ms", 0),
        delete_after_run=bool(d.get("delete_after_run", False)),
    )


class CronService:
    """Service for managing and executing scheduled jobs.

    Supports two modes:
    - **FS mode** (default): jobs stored in a JSON file on disk.
    - **DB mode** (when ``cron_repo`` is provided): jobs stored in the database
      with per-user isolation.
    """

    def __init__(
        self,
        store_path: Path | None = None,
        on_job: Callable[[CronJob], Coroutine[Any, Any, str | None]] | None = None,
        *,
        cron_repo: SQLiteCronRepository | None = None,
    ):
        self.store_path = store_path
        self.on_job = on_job
        self._cron_repo = cron_repo
        self._mode = "db" if cron_repo else "fs"
        self._store: CronStore | None = None
        self._timer_task: asyncio.Task | None = None
        self._running = False

    def _load_store(self) -> CronStore:
        """Load jobs from disk (FS mode only)."""
        if self._store:
            return self._store

        if self.store_path and self.store_path.exists():
            try:
                data = json.loads(self.store_path.read_text(encoding="utf-8"))
                jobs = []
                for j in data.get("jobs", []):
                    jobs.append(CronJob(
                        id=j["id"],
                        name=j["name"],
                        enabled=j.get("enabled", True),
                        schedule=CronSchedule(
                            kind=j["schedule"]["kind"],
                            at_ms=j["schedule"].get("atMs"),
                            every_ms=j["schedule"].get("everyMs"),
                            expr=j["schedule"].get("expr"),
                            tz=j["schedule"].get("tz"),
                        ),
                        payload=CronPayload(
                            kind=j["payload"].get("kind", "agent_turn"),
                            message=j["payload"].get("message", ""),
                            deliver=j["payload"].get("deliver", False),
                            channel=j["payload"].get("channel"),
                            to=j["payload"].get("to"),
                        ),
                        state=CronJobState(
                            next_run_at_ms=j.get("state", {}).get("nextRunAtMs"),
                            last_run_at_ms=j.get("state", {}).get("lastRunAtMs"),
                            last_status=j.get("state", {}).get("lastStatus"),
                            last_error=j.get("state", {}).get("lastError"),
                        ),
                        created_at_ms=j.get("createdAtMs", 0),
                        updated_at_ms=j.get("updatedAtMs", 0),
                        delete_after_run=j.get("deleteAfterRun", False),
                    ))
                self._store = CronStore(jobs=jobs)
            except Exception as e:
                logger.warning("Failed to load cron store: {}", e)
                self._store = CronStore()
        else:
            self._store = CronStore()

        return self._store

    def _save_store(self) -> None:
        """Save jobs to disk (FS mode only)."""
        if not self._store or not self.store_path:
            return

        self.store_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": self._store.version,
            "jobs": [
                {
                    "id": j.id,
                    "name": j.name,
                    "enabled": j.enabled,
                    "schedule": {
                        "kind": j.schedule.kind,
                        "atMs": j.schedule.at_ms,
                        "everyMs": j.schedule.every_ms,
                        "expr": j.schedule.expr,
                        "tz": j.schedule.tz,
                    },
                    "payload": {
                        "kind": j.payload.kind,
                        "message": j.payload.message,
                        "deliver": j.payload.deliver,
                        "channel": j.payload.channel,
                        "to": j.payload.to,
                    },
                    "state": {
                        "nextRunAtMs": j.state.next_run_at_ms,
                        "lastRunAtMs": j.state.last_run_at_ms,
                        "lastStatus": j.state.last_status,
                        "lastError": j.state.last_error,
                    },
                    "createdAtMs": j.created_at_ms,
                    "updatedAtMs": j.updated_at_ms,
                    "deleteAfterRun": j.delete_after_run,
                }
                for j in self._store.jobs
            ]
        }

        self.store_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    async def start(self) -> None:
        """Start the cron service."""
        self._running = True
        if self._mode == "fs":
            self._load_store()
            self._recompute_next_runs()
            self._save_store()
        self._arm_timer()
        count = await self._job_count()
        logger.info("Cron service started ({} mode, {} jobs)", self._mode, count)

    def stop(self) -> None:
        """Stop the cron service."""
        self._running = False
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None

    def _recompute_next_runs(self) -> None:
        """Recompute next run times for all enabled jobs (FS mode)."""
        if not self._store:
            return
        now = _now_ms()
        for job in self._store.jobs:
            if job.enabled:
                job.state.next_run_at_ms = _compute_next_run(job.schedule, now)

    async def _get_next_wake_ms(self) -> int | None:
        """Get the earliest next run time across all jobs."""
        if self._mode == "db":
            due = await self._cron_repo.get_due_jobs(_now_ms() + 86_400_000)
            if due:
                times = [j["next_run_at_ms"] for j in due if j.get("next_run_at_ms")]
                return min(times) if times else None
            return None
        else:
            if not self._store:
                return None
            times = [j.state.next_run_at_ms for j in self._store.jobs
                     if j.enabled and j.state.next_run_at_ms]
            return min(times) if times else None

    def _arm_timer(self) -> None:
        """Schedule the next timer tick."""
        if self._timer_task:
            self._timer_task.cancel()

        if not self._running:
            return

        async def _schedule():
            next_wake = await self._get_next_wake_ms()
            if not next_wake or not self._running:
                await asyncio.sleep(60)
                if self._running:
                    await self._on_timer()
                return
            delay_ms = max(0, next_wake - _now_ms())
            await asyncio.sleep(delay_ms / 1000)
            if self._running:
                await self._on_timer()

        self._timer_task = asyncio.create_task(_schedule())

    async def _on_timer(self) -> None:
        """Handle timer tick - run due jobs."""
        now = _now_ms()

        if self._mode == "db":
            due_dicts = await self._cron_repo.get_due_jobs(now)
            due_jobs = [_dict_to_job(d) for d in due_dicts]
        else:
            if not self._store:
                return
            due_jobs = [
                j for j in self._store.jobs
                if j.enabled and j.state.next_run_at_ms and now >= j.state.next_run_at_ms
            ]

        for job in due_jobs:
            await self._execute_job(job)

        if self._mode == "fs":
            self._save_store()
        self._arm_timer()

    async def _execute_job(self, job: CronJob) -> None:
        """Execute a single job."""
        start_ms = _now_ms()
        logger.info("Cron: executing job '{}' ({}) for user '{}'", job.name, job.id, job.user_id or "default")

        try:
            if self.on_job:
                await self.on_job(job)
            job.state.last_status = "ok"
            job.state.last_error = None
            logger.info("Cron: job '{}' completed", job.name)
        except Exception as e:
            job.state.last_status = "error"
            job.state.last_error = str(e)
            logger.error("Cron: job '{}' failed: {}", job.name, e)

        job.state.last_run_at_ms = start_ms
        job.updated_at_ms = _now_ms()

        if job.schedule.kind == "at":
            if job.delete_after_run:
                if self._mode == "db":
                    await self._cron_repo.delete_job(job.user_id, job.id)
                else:
                    self._store.jobs = [j for j in self._store.jobs if j.id != job.id]
                return
            else:
                job.enabled = False
                job.state.next_run_at_ms = None
        else:
            job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())

        if self._mode == "db":
            await self._cron_repo.update_job_state(job.id, {
                "next_run_at_ms": job.state.next_run_at_ms,
                "last_run_at_ms": job.state.last_run_at_ms,
                "last_status": job.state.last_status,
                "last_error": job.state.last_error,
                "enabled": 1 if job.enabled else 0,
            }, user_id=job.user_id or None)

    async def _job_count(self) -> int:
        if self._mode == "db":
            all_due = await self._cron_repo.get_due_jobs(_now_ms() + 365 * 86_400_000)
            return len(all_due)
        store = self._load_store()
        return len(store.jobs)

    async def list_jobs(self, user_id: str = "", include_disabled: bool = False) -> list[CronJob]:
        """List jobs. In DB mode, scoped to user_id."""
        if self._mode == "db":
            rows = await self._cron_repo.list_jobs(user_id, include_disabled)
            return [_dict_to_job(r) for r in rows]
        else:
            store = self._load_store()
            jobs = store.jobs if include_disabled else [j for j in store.jobs if j.enabled]
            return sorted(jobs, key=lambda j: j.state.next_run_at_ms or float('inf'))

    async def add_job(
        self,
        name: str,
        schedule: CronSchedule,
        message: str,
        deliver: bool = False,
        channel: str | None = None,
        to: str | None = None,
        delete_after_run: bool = False,
        user_id: str = "",
    ) -> CronJob:
        """Add a new job."""
        _validate_schedule_for_add(schedule)
        now = _now_ms()

        job = CronJob(
            id=str(uuid.uuid4())[:8],
            name=name,
            user_id=user_id,
            enabled=True,
            schedule=schedule,
            payload=CronPayload(
                kind="agent_turn",
                message=message,
                deliver=deliver,
                channel=channel,
                to=to,
            ),
            state=CronJobState(next_run_at_ms=_compute_next_run(schedule, now)),
            created_at_ms=now,
            updated_at_ms=now,
            delete_after_run=delete_after_run,
        )

        if self._mode == "db":
            await self._cron_repo.save_job(_job_to_dict(job))
        else:
            store = self._load_store()
            store.jobs.append(job)
            self._save_store()

        self._arm_timer()
        logger.info("Cron: added job '{}' ({}) for user '{}'", name, job.id, user_id or "default")
        return job

    async def remove_job(self, job_id: str, user_id: str = "") -> bool:
        """Remove a job by ID."""
        if self._mode == "db":
            removed = await self._cron_repo.delete_job(user_id, job_id)
        else:
            store = self._load_store()
            before = len(store.jobs)
            store.jobs = [j for j in store.jobs if j.id != job_id]
            removed = len(store.jobs) < before
            if removed:
                self._save_store()

        if removed:
            self._arm_timer()
            logger.info("Cron: removed job {}", job_id)
        return removed

    async def enable_job(self, job_id: str, enabled: bool = True, user_id: str = "") -> CronJob | None:
        """Enable or disable a job."""
        if self._mode == "db":
            job_dict = await self._cron_repo.get_job(user_id, job_id)
            if not job_dict:
                return None
            next_run = _compute_next_run(
                _dict_to_job(job_dict).schedule, _now_ms()
            ) if enabled else None
            await self._cron_repo.update_job_state(job_id, {
                "enabled": 1 if enabled else 0,
                "next_run_at_ms": next_run,
            }, user_id=user_id or None)
            job_dict = await self._cron_repo.get_job(user_id, job_id)
            self._arm_timer()
            return _dict_to_job(job_dict) if job_dict else None
        else:
            store = self._load_store()
            for job in store.jobs:
                if job.id == job_id:
                    job.enabled = enabled
                    job.updated_at_ms = _now_ms()
                    if enabled:
                        job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())
                    else:
                        job.state.next_run_at_ms = None
                    self._save_store()
                    self._arm_timer()
                    return job
            return None

    async def run_job(self, job_id: str, force: bool = False, user_id: str = "") -> bool:
        """Manually run a job."""
        if self._mode == "db":
            job_dict = await self._cron_repo.get_job(user_id, job_id)
            if not job_dict:
                return False
            job = _dict_to_job(job_dict)
            if not force and not job.enabled:
                return False
            await self._execute_job(job)
            self._arm_timer()
            return True
        else:
            store = self._load_store()
            for job in store.jobs:
                if job.id == job_id:
                    if not force and not job.enabled:
                        return False
                    await self._execute_job(job)
                    self._save_store()
                    self._arm_timer()
                    return True
            return False

    def status(self) -> dict:
        """Get service status (sync, for CLI display)."""
        if self._mode == "db":
            return {
                "enabled": self._running,
                "mode": "db",
                "jobs": -1,  # Unknown without async query
            }
        store = self._load_store()
        return {
            "enabled": self._running,
            "mode": "fs",
            "jobs": len(store.jobs),
        }
