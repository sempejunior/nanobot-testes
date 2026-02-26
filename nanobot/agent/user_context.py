"""User context for multi-tenant agent processing.

Each user gets an isolated ``UserContext`` containing their own
SessionManager, MemoryStore, SkillsLoader, ToolRegistry, and agent settings.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nanobot.agent.context import ContextBuilder
from nanobot.agent.memory import MemoryStore
from nanobot.agent.skills import BUILTIN_SKILLS_DIR, SkillsLoader
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.session.manager import SessionManager

if TYPE_CHECKING:
    from nanobot.bus.queue import MessageBus
    from nanobot.cron.service import CronService
    from nanobot.db.factory import RepositoryFactory
    from nanobot.providers.base import LLMProvider


@dataclass
class UserContext:
    """Per-user runtime state built from the users table."""

    user_id: str
    sessions: SessionManager
    context: ContextBuilder
    memory: MemoryStore
    skills: SkillsLoader
    tools: ToolRegistry

    model: str
    max_tokens: int
    temperature: float
    max_iterations: int
    memory_window: int

    provider: LLMProvider | None = None
    limits: dict[str, Any] = field(default_factory=dict)


def _make_user_provider(agent_config: dict[str, Any]) -> LLMProvider | None:
    """Build a per-user LLM provider from agent_config['provider'], or None."""
    provider_cfg = agent_config.get("provider", {})
    name = provider_cfg.get("name", "")
    api_key = provider_cfg.get("api_key", "")
    if not name or not api_key:
        return None
    api_base = provider_cfg.get("api_base") or None
    model = agent_config.get("model", "")
    if name == "custom":
        from nanobot.providers.custom_provider import CustomProvider
        return CustomProvider(
            api_key=api_key,
            api_base=api_base or "http://localhost:8000/v1",
            default_model=model or "default",
        )
    from nanobot.providers.litellm_provider import LiteLLMProvider
    return LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=model or f"{name}/default",
        provider_name=name,
    )


async def build_user_context(
    user_id: str,
    repos: RepositoryFactory,
    workspace: Path,
    bus: MessageBus,
    *,
    brave_api_key: str | None = None,
    cron_service: CronService | None = None,
    builtin_skills_dir: Path | None = None,
) -> UserContext:
    """Build a UserContext from the user's DB record.

    Raises:
        ValueError: If the user_id is not found in the database.
    """
    user_doc = await repos.users.get_by_id(user_id)
    if not user_doc:
        raise ValueError(f"User not found: {user_id}")

    agent_config: dict[str, Any] = user_doc.get("agent_config", {})
    tools_enabled: list[str] = user_doc.get("tools_enabled", [])
    limits: dict[str, Any] = user_doc.get("limits", {})

    memory = MemoryStore(memory_repo=repos.memories, user_id=user_id)
    skills = SkillsLoader(
        skill_repo=repos.skills,
        user_id=user_id,
        builtin_skills_dir=builtin_skills_dir or BUILTIN_SKILLS_DIR,
    )
    sessions = SessionManager(
        session_repo=repos.sessions,
        message_repo=repos.messages,
        user_id=user_id,
    )
    context = ContextBuilder(
        workspace,
        memory_store=memory,
        skills_loader=skills,
        user_repo=repos.users,
        user_id=user_id,
        language=agent_config.get("language", ""),
        custom_instructions=agent_config.get("custom_instructions", ""),
    )
    tools = build_tool_registry(
        tools_enabled=tools_enabled,
        workspace=workspace,
        bus=bus,
        brave_api_key=brave_api_key,
        exec_timeout=limits.get("max_exec_timeout_s", 30),
        restrict_to_workspace=True,
        cron_service=cron_service,
        user_id=user_id,
        skill_repo=repos.skills,
        memory_store=memory,
    )

    return UserContext(
        user_id=user_id,
        sessions=sessions,
        context=context,
        memory=memory,
        skills=skills,
        tools=tools,
        model=agent_config.get("model", "anthropic/claude-sonnet-4-20250514"),
        max_tokens=agent_config.get("max_tokens", 8192),
        temperature=agent_config.get("temperature", 0.1),
        max_iterations=agent_config.get("max_tool_iterations", 40),
        memory_window=agent_config.get("memory_window", 100),
        provider=_make_user_provider(agent_config),
        limits=limits,
    )


def build_tool_registry(
    tools_enabled: list[str],
    workspace: Path,
    bus: MessageBus,
    *,
    brave_api_key: str | None = None,
    exec_timeout: int = 30,
    restrict_to_workspace: bool = True,
    cron_service: CronService | None = None,
    user_id: str | None = None,
    skill_repo: Any | None = None,
    memory_store: Any | None = None,
) -> ToolRegistry:
    """Build a ToolRegistry with only the enabled tools."""
    from nanobot.agent.tools.cron import CronTool
    from nanobot.agent.tools.filesystem import (
        EditFileTool,
        ListDirTool,
        ReadFileTool,
        WriteFileTool,
    )
    from nanobot.agent.tools.message import MessageTool
    from nanobot.agent.tools.shell import ExecTool
    from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
    from nanobot.agent.tools.skill import SaveSkillTool

    registry = ToolRegistry()
    allowed_dir = workspace if restrict_to_workspace else None

    factories: dict[str, Any] = {
        "read_file": lambda: ReadFileTool(workspace=workspace, allowed_dir=allowed_dir),
        "write_file": lambda: WriteFileTool(workspace=workspace, allowed_dir=allowed_dir),
        "edit_file": lambda: EditFileTool(workspace=workspace, allowed_dir=allowed_dir),
        "list_dir": lambda: ListDirTool(workspace=workspace, allowed_dir=allowed_dir),
        "exec": lambda: ExecTool(
            working_dir=str(workspace),
            timeout=exec_timeout,
            restrict_to_workspace=restrict_to_workspace,
        ),
        "web_search": lambda: WebSearchTool(api_key=brave_api_key),
        "web_fetch": lambda: WebFetchTool(),
        "message": lambda: MessageTool(send_callback=bus.publish_outbound),
        "save_skill": lambda: SaveSkillTool(user_id=user_id, skill_repo=skill_repo, workspace=workspace),
    }

    if memory_store:
        from nanobot.agent.tools.memory import SaveMemoryTool, SearchMemoryTool
        factories["save_memory"] = lambda: SaveMemoryTool(memory_store)
        factories["search_memory"] = lambda: SearchMemoryTool(memory_store)

    if cron_service:
        factories["cron"] = lambda: CronTool(cron_service)

    if os.environ.get("DISPLAY"):
        from nanobot.agent.tools.computer import ComputerTool
        from nanobot.agent.tools.browser import BrowserTool
        factories["computer"] = lambda: ComputerTool()
        factories["browser"] = lambda: BrowserTool()

    for name in tools_enabled:
        factory = factories.get(name)
        if factory:
            tool = factory()
            if tool is not None:
                registry.register(tool)

    if memory_store:
        if not registry.has("save_memory"):
            registry.register(SaveMemoryTool(memory_store))
        if not registry.has("search_memory"):
            registry.register(SearchMemoryTool(memory_store))

    if os.environ.get("DISPLAY"):
        from nanobot.agent.tools.screenshot import ScreenshotTool
        registry.register(ScreenshotTool())

    return registry


class RateLimiter:
    """Simple rate limiter: in-memory sliding window + DB daily counters."""

    def __init__(self, repos: RepositoryFactory):
        self._repos = repos
        self._recent: dict[str, list[float]] = {}

    async def check(self, user_id: str) -> str | None:
        """Check rate limits. Returns error message if exceeded, None if OK."""
        user = await self._repos.users.get_by_id(user_id)
        if not user:
            return "User not found."

        limits: dict[str, Any] = user.get("limits", {})

        max_tokens_day = limits.get("max_tokens_per_day", 1_000_000)
        if user.get("tokens_today", 0) >= max_tokens_day:
            return "Daily token limit exceeded. Try again tomorrow."

        max_rpm = limits.get("max_requests_per_minute", 30)
        now = time.time()
        recent = self._recent.get(user_id, [])
        recent = [t for t in recent if now - t < 60]
        self._recent[user_id] = recent

        if len(recent) >= max_rpm:
            return f"Rate limit exceeded ({max_rpm} requests/minute). Please wait."

        return None

    def record_request(self, user_id: str) -> None:
        """Record a request timestamp for rate limiting."""
        self._recent.setdefault(user_id, []).append(time.time())

    async def record_usage(self, user_id: str, tokens: int) -> None:
        """Record token usage in DB."""
        await self._repos.users.increment_usage(user_id, tokens)
