"""Session management for conversation history."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from loguru import logger

from nanobot.utils.helpers import ensure_dir, safe_filename

if TYPE_CHECKING:
    from nanobot.db.repositories import MessageRepository, SessionRepository


@dataclass
class Session:
    """
    A conversation session.

    Stores messages in JSONL format for easy reading and persistence.

    Important: Messages are append-only for LLM cache efficiency.
    The consolidation process writes summaries to MEMORY.md/HISTORY.md
    but does NOT modify the messages list or get_history() output.
    """

    key: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_consolidated: int = 0

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()

    def get_history(self, max_messages: int = 500) -> list[dict[str, Any]]:
        """Return unconsolidated messages for LLM input, aligned to a user turn."""
        unconsolidated = self.messages[self.last_consolidated:]
        sliced = unconsolidated[-max_messages:]

        for i, m in enumerate(sliced):
            if m.get("role") == "user":
                sliced = sliced[i:]
                break

        out: list[dict[str, Any]] = []
        for m in sliced:
            entry: dict[str, Any] = {"role": m["role"], "content": m.get("content", "")}
            for k in ("tool_calls", "tool_call_id", "name"):
                if k in m:
                    entry[k] = m[k]
            out.append(entry)
        return out

    def clear(self) -> None:
        """Clear all messages and reset session to initial state."""
        self.messages = []
        self.last_consolidated = 0
        self.updated_at = datetime.now()


class SessionManager:
    """
    Manages conversation sessions.

    Supports two modes:
    - Filesystem mode: sessions stored as JSONL files (backward compatible)
    - DB mode: sessions stored via SessionRepository + MessageRepository
    """

    def __init__(
        self,
        workspace: Path | None = None,
        *,
        session_repo: SessionRepository | None = None,
        message_repo: MessageRepository | None = None,
        user_id: str | None = None,
    ):
        if session_repo is not None:
            self._mode = "db"
            self._session_repo = session_repo
            self._message_repo = message_repo
            self._user_id = user_id
        elif workspace is not None:
            self._mode = "fs"
            self.workspace = workspace
            self.sessions_dir = ensure_dir(workspace / "sessions")
            self.legacy_sessions_dir = Path.home() / ".nanobot" / "sessions"
        else:
            raise ValueError("Either workspace or session_repo+message_repo must be provided")

        self._cache: dict[str, Session] = {}
        self._session_ids: dict[str, int] = {}
        self._loaded_counts: dict[str, int] = {}


    async def get_or_create(self, key: str) -> Session:
        """Get an existing session or create a new one."""
        if key in self._cache:
            return self._cache[key]

        if self._mode == "db":
            session = await self._load_from_db(key)
        else:
            session = self._load_from_fs(key)

        if session is None:
            session = Session(key=key)
            self._loaded_counts[key] = 0

        self._cache[key] = session
        return session

    async def save(self, session: Session) -> None:
        """Save a session (to DB or filesystem)."""
        if self._mode == "db":
            await self._save_to_db(session)
        else:
            self._save_to_fs(session)
        self._cache[session.key] = session

    async def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions."""
        if self._mode == "db":
            return await self._session_repo.list_sessions(self._user_id)
        return self._list_sessions_fs()

    async def delete(self, key: str) -> bool:
        """Delete a session."""
        if self._mode == "db":
            ok = await self._session_repo.delete(self._user_id, key)
            self._cache.pop(key, None)
            self._session_ids.pop(key, None)
            self._loaded_counts.pop(key, None)
            return ok

        path = self._get_session_path(key)
        self._cache.pop(key, None)
        if path.exists():
            path.unlink()
            return True
        return False

    def invalidate(self, key: str) -> None:
        """Remove a session from the in-memory cache."""
        self._cache.pop(key, None)
        self._session_ids.pop(key, None)
        self._loaded_counts.pop(key, None)

    async def _load_from_db(self, key: str) -> Session | None:
        row = await self._session_repo.get(self._user_id, key)
        if not row:
            return None

        session_id = row["id"]
        db_messages = await self._message_repo.get_messages(session_id)

        messages = [self._db_msg_to_session_msg(m) for m in db_messages]

        self._session_ids[key] = session_id
        self._loaded_counts[key] = len(messages)

        return Session(
            key=key,
            messages=messages,
            created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row.get("created_at"), str) else datetime.now(),
            last_consolidated=row.get("last_consolidated", 0),
        )

    async def _save_to_db(self, session: Session) -> None:
        session_id = await self._session_repo.save({
            "user_id": self._user_id,
            "session_key": session.key,
            "last_consolidated": session.last_consolidated,
            "message_count": len(session.messages),
        })
        self._session_ids[session.key] = session_id

        loaded = self._loaded_counts.get(session.key, 0)
        current = len(session.messages)

        if current < loaded:
            await self._message_repo.delete_all(session_id)
            if session.messages:
                await self._message_repo.append_many(
                    session_id, self._user_id, session.messages,
                )
        elif current > loaded:
            new_msgs = session.messages[loaded:]
            await self._message_repo.append_many(
                session_id, self._user_id, new_msgs,
            )

        self._loaded_counts[session.key] = len(session.messages)

    @staticmethod
    def _db_msg_to_session_msg(m: dict[str, Any]) -> dict[str, Any]:
        """Convert a DB message row to a Session-compatible message dict."""
        msg: dict[str, Any] = {"role": m["role"], "content": m.get("content")}
        for k in ("tool_calls", "tool_call_id", "name"):
            if m.get(k):
                msg[k] = m[k]
        msg["timestamp"] = m.get("created_at", "")
        return msg

    def _get_session_path(self, key: str) -> Path:
        safe_key = safe_filename(key.replace(":", "_"))
        return self.sessions_dir / f"{safe_key}.jsonl"

    def _get_legacy_session_path(self, key: str) -> Path:
        safe_key = safe_filename(key.replace(":", "_"))
        return self.legacy_sessions_dir / f"{safe_key}.jsonl"

    def _load_from_fs(self, key: str) -> Session | None:
        path = self._get_session_path(key)
        if not path.exists():
            legacy_path = self._get_legacy_session_path(key)
            if legacy_path.exists():
                try:
                    shutil.move(str(legacy_path), str(path))
                    logger.info("Migrated session {} from legacy path", key)
                except Exception:
                    logger.exception("Failed to migrate session {}", key)

        if not path.exists():
            return None

        try:
            messages = []
            metadata = {}
            created_at = None
            last_consolidated = 0

            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)

                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
                        last_consolidated = data.get("last_consolidated", 0)
                    else:
                        messages.append(data)

            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                metadata=metadata,
                last_consolidated=last_consolidated,
            )
        except Exception as e:
            logger.warning("Failed to load session {}: {}", key, e)
            return None

    def _save_to_fs(self, session: Session) -> None:
        path = self._get_session_path(session.key)
        with open(path, "w", encoding="utf-8") as f:
            metadata_line = {
                "_type": "metadata",
                "key": session.key,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "metadata": session.metadata,
                "last_consolidated": session.last_consolidated,
            }
            f.write(json.dumps(metadata_line, ensure_ascii=False) + "\n")
            for msg in session.messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def _list_sessions_fs(self) -> list[dict[str, Any]]:
        sessions = []
        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                with open(path, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            key = data.get("key") or path.stem.replace("_", ":", 1)
                            sessions.append({
                                "key": key,
                                "created_at": data.get("created_at"),
                                "updated_at": data.get("updated_at"),
                                "path": str(path),
                            })
            except Exception:
                continue
        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
