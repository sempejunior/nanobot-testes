"""Tools for explicit memory operations (save facts, search history)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.agent.memory import MemoryStore


class SaveMemoryTool(Tool):
    """Tool that saves important facts to the user's long-term memory via MemoryStore."""

    def __init__(self, memory_store: MemoryStore):
        self._memory = memory_store

    @property
    def name(self) -> str:
        return "save_memory"

    @property
    def description(self) -> str:
        return (
            "Save an important fact to long-term memory. Use this when the user asks you "
            "to remember something, or when you learn an important preference, relationship, "
            "or project detail. The fact will persist across sessions."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "fact": {
                    "type": "string",
                    "description": (
                        "The fact to remember, as a concise markdown line "
                        "(e.g. '- User's name is Carlos', '- Project uses OAuth2')."
                    ),
                },
            },
            "required": ["fact"],
        }

    async def execute(self, **kwargs: Any) -> str:
        fact = kwargs.get("fact", "").strip()
        if not fact:
            return "Error: 'fact' is required."

        try:
            current = await self._memory.read_long_term()
            if current:
                updated = current.rstrip() + "\n" + fact + "\n"
            else:
                updated = "# Long-term Memory\n\n" + fact + "\n"

            await self._memory.write_long_term(updated)
            return f"Memorized: {fact}"
        except Exception as e:
            return f"Error saving memory: {e}"


class SearchMemoryTool(Tool):
    """Tool that searches the user's conversation history via MemoryStore."""

    def __init__(self, memory_store: MemoryStore):
        self._memory = memory_store

    @property
    def name(self) -> str:
        return "search_memory"

    @property
    def description(self) -> str:
        return (
            "Search past conversation history for events, decisions, or topics. "
            "Returns matching history entries. Use this to recall what happened in "
            "previous sessions."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keyword or phrase to search for in conversation history.",
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> str:
        query = kwargs.get("query", "").strip()
        if not query:
            return "Error: 'query' is required."

        try:
            results = await self._memory.search_history(query)
            if not results:
                return f"No history entries found matching '{query}'."
            return "\n\n".join(results)
        except Exception as e:
            return f"Error searching memory: {e}"
