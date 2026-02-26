"""Memory system for persistent agent memory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from nanobot.utils.helpers import ensure_dir

if TYPE_CHECKING:
    from nanobot.db.repositories import MemoryRepository
    from nanobot.providers.base import LLMProvider
    from nanobot.session.manager import Session


_SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save the memory consolidation result to persistent storage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "history_entry": {
                        "type": "string",
                        "description": "A paragraph (2-5 sentences) summarizing key events/decisions/topics. "
                        "Start with [YYYY-MM-DD HH:MM]. Include detail useful for grep search.",
                    },
                    "memory_update": {
                        "type": "string",
                        "description": "Full updated long-term memory as markdown. Include all existing "
                        "facts plus new ones. Return unchanged if nothing new.",
                    },
                },
                "required": ["history_entry", "memory_update"],
            },
        },
    }
]


class MemoryStore:
    """Two-layer memory: MEMORY.md (long-term facts) + HISTORY.md (grep-searchable log).

    Supports two modes:
    - Filesystem mode: reads/writes MEMORY.md and HISTORY.md files (backward compatible)
    - DB mode: uses MemoryRepository for persistence
    """

    def __init__(
        self,
        workspace: Path | None = None,
        *,
        memory_repo: MemoryRepository | None = None,
        user_id: str | None = None,
    ):
        if memory_repo is not None:
            self._mode = "db"
            self._repo = memory_repo
            self._user_id = user_id
        elif workspace is not None:
            self._mode = "fs"
            self.memory_dir = ensure_dir(workspace / "memory")
            self.memory_file = self.memory_dir / "MEMORY.md"
            self.history_file = self.memory_dir / "HISTORY.md"
        else:
            raise ValueError("Either workspace or memory_repo must be provided")

    async def read_long_term(self) -> str:
        if self._mode == "db":
            return await self._repo.get_long_term(self._user_id)
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    async def write_long_term(self, content: str) -> None:
        if self._mode == "db":
            await self._repo.save_long_term(self._user_id, content)
        else:
            self.memory_file.write_text(content, encoding="utf-8")

    async def append_history(self, entry: str) -> None:
        if self._mode == "db":
            await self._repo.append_history(self._user_id, entry)
        else:
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(entry.rstrip() + "\n\n")

    async def search_history(self, query: str, limit: int = 20) -> list[str]:
        """Search conversation history for matching entries."""
        if self._mode == "db":
            results = await self._repo.search_history(self._user_id, query, limit)
            if not results:
                return []
            return [r["content"] if isinstance(r, dict) else r for r in results]
        else:
            if not self.history_file.exists():
                return []
            content = self.history_file.read_text(encoding="utf-8")
            query_lower = query.lower()
            matches = [
                line for line in content.split("\n\n")
                if query_lower in line.lower()
            ]
            return matches[:limit]

    async def get_memory_context(self) -> str:
        long_term = await self.read_long_term()
        return f"## Long-term Memory\n{long_term}" if long_term else ""

    async def consolidate(
        self,
        session: Session,
        provider: LLMProvider,
        model: str,
        *,
        archive_all: bool = False,
        memory_window: int = 50,
    ) -> bool:
        """Consolidate old messages into memory via LLM tool call.

        Returns True on success (including no-op), False on failure.
        """
        if archive_all:
            old_messages = session.messages
            keep_count = 0
            logger.info("Memory consolidation (archive_all): {} messages", len(session.messages))
        else:
            keep_count = memory_window // 2
            if len(session.messages) <= keep_count:
                return True
            if len(session.messages) - session.last_consolidated <= 0:
                return True
            old_messages = session.messages[session.last_consolidated:-keep_count]
            if not old_messages:
                return True
            logger.info("Memory consolidation: {} to consolidate, {} keep", len(old_messages), keep_count)

        lines = []
        for m in old_messages:
            if not m.get("content"):
                continue
            tools = f" [tools: {', '.join(m['tools_used'])}]" if m.get("tools_used") else ""
            lines.append(f"[{m.get('timestamp', '?')[:16]}] {m['role'].upper()}{tools}: {m['content']}")

        current_memory = await self.read_long_term()
        prompt = f"""Process this conversation and call the save_memory tool with your consolidation.

## Current Long-term Memory
{current_memory or "(empty)"}

## Conversation to Process
{chr(10).join(lines)}"""

        try:
            response = await provider.chat(
                messages=[
                    {"role": "system", "content": "You are a memory consolidation agent. Call the save_memory tool with your consolidation of the conversation."},
                    {"role": "user", "content": prompt},
                ],
                tools=_SAVE_MEMORY_TOOL,
                model=model,
            )

            if not response.has_tool_calls:
                logger.warning("Memory consolidation: LLM did not call save_memory, skipping")
                return False

            args = response.tool_calls[0].arguments
            if isinstance(args, str):
                args = json.loads(args)
            if not isinstance(args, dict):
                logger.warning("Memory consolidation: unexpected arguments type {}", type(args).__name__)
                return False

            if entry := args.get("history_entry"):
                if not isinstance(entry, str):
                    entry = json.dumps(entry, ensure_ascii=False)
                await self.append_history(entry)
            if update := args.get("memory_update"):
                if not isinstance(update, str):
                    update = json.dumps(update, ensure_ascii=False)
                if update != current_memory:
                    await self.write_long_term(update)

            session.last_consolidated = 0 if archive_all else len(session.messages) - keep_count
            logger.info("Memory consolidation done: {} messages, last_consolidated={}", len(session.messages), session.last_consolidated)
            return True
        except Exception:
            logger.exception("Memory consolidation failed")
            return False
