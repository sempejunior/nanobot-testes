"""Repository interfaces (Protocols) for pluggable storage backends.

These Protocols define the contract between the application layer and the
persistence layer.  The application only imports these interfaces; the actual
implementation (SQLite today, MongoDB tomorrow) is injected at startup.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable



@runtime_checkable
class UserRepository(Protocol):
    """CRUD + usage tracking for user accounts."""

    async def get_by_id(self, user_id: str) -> dict[str, Any] | None: ...

    async def get_by_api_key_hash(self, key_hash: str) -> dict[str, Any] | None: ...

    async def get_by_email(self, email: str) -> dict[str, Any] | None: ...

    async def create(self, user: dict[str, Any]) -> str:
        """Create a user and return the user_id."""
        ...

    async def update(self, user_id: str, fields: dict[str, Any]) -> bool: ...

    async def list_all(self, status: str | None = None) -> list[dict[str, Any]]: ...

    async def increment_usage(self, user_id: str, tokens: int, requests: int = 1) -> None: ...

    async def reset_daily_usage(self) -> int:
        """Reset daily counters for all users. Returns number of rows affected."""
        ...



@runtime_checkable
class SessionRepository(Protocol):
    """Session metadata CRUD (messages stored separately)."""

    async def get(self, user_id: str, session_key: str) -> dict[str, Any] | None: ...

    async def save(self, session: dict[str, Any]) -> int:
        """Upsert session. Returns the session row id."""
        ...

    async def list_sessions(self, user_id: str, status: str = "active") -> list[dict[str, Any]]: ...

    async def delete(self, user_id: str, session_key: str) -> bool: ...

    async def update_status(self, user_id: str, session_key: str, status: str) -> bool: ...



@runtime_checkable
class MessageRepository(Protocol):
    """Per-session message storage."""

    async def get_messages(
        self, session_id: int, *, offset: int = 0, limit: int = 5000,
    ) -> list[dict[str, Any]]: ...

    async def append(self, session_id: int, user_id: str, message: dict[str, Any]) -> int:
        """Append a message and return its id."""
        ...

    async def append_many(self, session_id: int, user_id: str, messages: list[dict[str, Any]]) -> None: ...

    async def count(self, session_id: int) -> int: ...

    async def delete_all(self, session_id: int) -> int:
        """Delete all messages for a session. Returns count deleted."""
        ...



@runtime_checkable
class MemoryRepository(Protocol):
    """Two-layer memory: long_term (1 per user) + history (N per user)."""

    async def get_long_term(self, user_id: str) -> str: ...

    async def save_long_term(self, user_id: str, content: str) -> None: ...

    async def append_history(self, user_id: str, entry: str) -> None: ...

    async def get_history(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]: ...

    async def search_history(self, user_id: str, query: str, limit: int = 50) -> list[dict[str, Any]]: ...

    async def delete_history(self, user_id: str, entry_id: int) -> bool: ...

    async def clear_history(self, user_id: str) -> int: ...



@runtime_checkable
class SkillRepository(Protocol):
    """Per-user skill storage (builtins stay on filesystem)."""

    async def list_skills(self, user_id: str, enabled_only: bool = True) -> list[dict[str, Any]]: ...

    async def get_skill(self, user_id: str, name: str) -> dict[str, Any] | None: ...

    async def save_skill(self, user_id: str, skill: dict[str, Any]) -> None: ...

    async def delete_skill(self, user_id: str, name: str) -> bool: ...

    async def count_skills(self, user_id: str) -> int: ...



@runtime_checkable
class CronRepository(Protocol):
    """Per-user cron job storage."""

    async def list_jobs(self, user_id: str, include_disabled: bool = False) -> list[dict[str, Any]]: ...

    async def get_job(self, user_id: str, job_id: str) -> dict[str, Any] | None: ...

    async def get_due_jobs(self, now_ms: int) -> list[dict[str, Any]]:
        """Cross-user: all enabled jobs whose next_run_at_ms <= now_ms."""
        ...

    async def save_job(self, job: dict[str, Any]) -> None: ...

    async def delete_job(self, user_id: str, job_id: str) -> bool: ...

    async def update_job_state(self, job_id: str, state: dict[str, Any], *, user_id: str | None = None) -> None: ...

    async def count_jobs(self, user_id: str) -> int: ...



@runtime_checkable
class ChannelBindingRepository(Protocol):
    """Maps external sender_id (per channel) to internal user_id."""

    async def resolve_user(self, channel: str, sender_id: str) -> str | None: ...

    async def bind(self, user_id: str, channel: str, sender_id: str) -> None: ...

    async def unbind(self, user_id: str, channel: str, sender_id: str) -> bool: ...

    async def list_bindings(self, user_id: str) -> list[dict[str, Any]]: ...



@runtime_checkable
class AuditRepository(Protocol):
    """Append-only audit trail with TTL cleanup."""

    async def log(self, user_id: str, event: str, detail: dict[str, Any] | None = None,
                  ip_address: str | None = None, user_agent: str | None = None) -> None: ...

    async def query(
        self, *, user_id: str | None = None, event: str | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[dict[str, Any]]: ...

    async def cleanup(self, days: int = 90) -> int:
        """Delete entries older than *days*. Returns count deleted."""
        ...
