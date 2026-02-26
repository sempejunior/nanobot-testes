"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import AsyncExitStack
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from loguru import logger

from nanobot.agent.context import ContextBuilder
from nanobot.agent.memory import MemoryStore
from nanobot.agent.subagent import SubagentManager
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.memory import SaveMemoryTool, SearchMemoryTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.session.manager import Session, SessionManager

if TYPE_CHECKING:
    from nanobot.config.schema import ChannelsConfig, ExecToolConfig
    from nanobot.cron.service import CronService
    from nanobot.db.factory import RepositoryFactory
    from nanobot.agent.user_context import UserContext


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back

    Supports two modes:
    - **FS mode** (default): single-user, filesystem-backed sessions/memory.
    - **DB mode** (when ``repos`` is provided): multi-user with per-user
      isolation via UserContext, rate limiting, and channel binding resolution.
    """

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 40,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        memory_window: int = 20,
        brave_api_key: str | None = None,
        exec_config: ExecToolConfig | None = None,
        cron_service: CronService | None = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        mcp_servers: dict | None = None,
        channels_config: ChannelsConfig | None = None,
        repos: RepositoryFactory | None = None,
    ):
        from nanobot.config.schema import ExecToolConfig
        self.bus = bus
        self.channels_config = channels_config
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.memory_window = memory_window
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace

        self._repos = repos
        self._user_contexts: dict[str, UserContext] = {}
        if repos:
            from nanobot.agent.user_context import RateLimiter
            self._rate_limiter: RateLimiter | None = RateLimiter(repos)
        else:
            self._rate_limiter = None

        self.context = ContextBuilder(workspace)
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
        )

        self._running = False
        self._mcp_servers = mcp_servers or {}
        self._mcp_stack: AsyncExitStack | None = None
        self._mcp_connected = False
        self._mcp_connecting = False
        self._consolidating: set[str] = set()
        self._consolidation_tasks: set[asyncio.Task] = set()
        self._consolidation_locks: dict[str, asyncio.Lock] = {}
        if not self._repos:
            self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of tools (FS mode only)."""
        import os
        from nanobot.agent.tools.skill import SaveSkillTool
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        for cls in (ReadFileTool, WriteFileTool, EditFileTool, ListDirTool):
            self.tools.register(cls(workspace=self.workspace, allowed_dir=allowed_dir))
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.restrict_to_workspace,
        ))
        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(WebFetchTool())
        self.tools.register(MessageTool(send_callback=self.bus.publish_outbound))
        self.tools.register(SpawnTool(manager=self.subagents))
        self.tools.register(SaveSkillTool(workspace=self.workspace))
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))
        fs_memory = MemoryStore(self.workspace)
        self.tools.register(SaveMemoryTool(fs_memory))
        self.tools.register(SearchMemoryTool(fs_memory))
        if os.environ.get("DISPLAY"):
            from nanobot.agent.tools.screenshot import ScreenshotTool
            from nanobot.agent.tools.computer import ComputerTool
            self.tools.register(ScreenshotTool())
            self.tools.register(ComputerTool())
            from nanobot.agent.tools.browser import BrowserTool, cdp_available
            if cdp_available():
                self.tools.register(BrowserTool())

    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers (one-time, lazy)."""
        if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
            return
        self._mcp_connecting = True
        from nanobot.agent.tools.mcp import connect_mcp_servers
        try:
            self._mcp_stack = AsyncExitStack()
            await self._mcp_stack.__aenter__()
            await connect_mcp_servers(self._mcp_servers, self.tools, self._mcp_stack)
            self._mcp_connected = True
        except Exception as e:
            logger.error("Failed to connect MCP servers (will retry next message): {}", e)
            if self._mcp_stack:
                try:
                    await self._mcp_stack.aclose()
                except Exception:
                    pass
                self._mcp_stack = None
        finally:
            self._mcp_connecting = False

    def _set_tool_context(
        self, channel: str, chat_id: str, message_id: str | None = None,
        *, tools: ToolRegistry | None = None, user_id: str = "",
    ) -> None:
        """Update context for all tools that need routing info."""
        _tools = tools or self.tools
        if message_tool := _tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.set_context(channel, chat_id, message_id)

        if spawn_tool := _tools.get("spawn"):
            if isinstance(spawn_tool, SpawnTool):
                spawn_tool.set_context(channel, chat_id)

        if cron_tool := _tools.get("cron"):
            if isinstance(cron_tool, CronTool):
                cron_tool.set_context(channel, chat_id, user_id=user_id)

    @staticmethod
    def _strip_think(text: str | None) -> str | None:
        """Remove <think>…</think> blocks that some models embed in content."""
        if not text:
            return None
        return re.sub(r"<think>[\s\S]*?</think>", "", text).strip() or None

    @staticmethod
    def _tool_hint(tool_calls: list) -> str:
        """Format tool calls as concise hint, e.g. 'web_search("query")'."""
        def _fmt(tc):
            val = next(iter(tc.arguments.values()), None) if tc.arguments else None
            if not isinstance(val, str):
                return tc.name
            return f'{tc.name}("{val[:40]}…")' if len(val) > 40 else f'{tc.name}("{val}")'
        return ", ".join(_fmt(tc) for tc in tool_calls)

    async def _resolve_user_id(self, msg: InboundMessage) -> str | None:
        """Resolve user_id from the message or via ChannelBindingRepository."""
        if msg.user_id:
            return msg.user_id
        if self._repos:
            return await self._repos.channel_bindings.resolve_user(msg.channel, msg.sender_id)
        return None

    async def _get_user_context(self, user_id: str) -> "UserContext":
        """Get or build a cached UserContext for a user."""
        if user_id in self._user_contexts:
            return self._user_contexts[user_id]

        from nanobot.agent.user_context import build_user_context
        uctx = await build_user_context(
            user_id,
            self._repos,
            self.workspace,
            self.bus,
            brave_api_key=self.brave_api_key,
            cron_service=self.cron_service,
        )

        if self._mcp_connected:
            for name, tool in self.tools._tools.items():
                if name.startswith("mcp_") and not uctx.tools.has(name):
                    uctx.tools.register(tool)

        self._user_contexts[user_id] = uctx
        return uctx

    async def _run_agent_loop(
        self,
        initial_messages: list[dict],
        on_progress: Callable[..., Awaitable[None]] | None = None,
        *,
        tools: ToolRegistry | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_iterations: int | None = None,
        provider: LLMProvider | None = None,
    ) -> tuple[str | None, list[str], list[dict]]:
        """Run the agent iteration loop. Returns (final_content, tools_used, messages)."""
        _tools = tools or self.tools
        _provider = provider or self.provider
        _model = model or self.model
        _temp = temperature if temperature is not None else self.temperature
        _max_tokens = max_tokens or self.max_tokens
        _max_iter = max_iterations or self.max_iterations

        messages = initial_messages
        iteration = 0
        final_content = None
        tools_used: list[str] = []

        while iteration < _max_iter:
            iteration += 1

            response = await _provider.chat(
                messages=messages,
                tools=_tools.get_definitions(),
                model=_model,
                temperature=_temp,
                max_tokens=_max_tokens,
            )

            if response.has_tool_calls:
                if on_progress:
                    clean = self._strip_think(response.content)
                    if clean:
                        await on_progress(clean)
                    await on_progress(self._tool_hint(response.tool_calls), tool_hint=True)

                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )

                for tool_call in response.tool_calls:
                    tools_used.append(tool_call.name)
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info("Tool call: {}({})", tool_call.name, args_str[:200])
                    result = await _tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                final_content = self._strip_think(response.content)
                break

        if final_content is None and iteration >= _max_iter:
            logger.warning("Max iterations ({}) reached", _max_iter)
            final_content = (
                f"I reached the maximum number of tool call iterations ({_max_iter}) "
                "without completing the task. You can try breaking the task into smaller steps."
            )

        return final_content, tools_used, messages

    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        await self._connect_mcp()
        logger.info("Agent loop started")

        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                try:
                    response = await self._process_message(msg)
                    if response is not None:
                        await self.bus.publish_outbound(response)
                    elif msg.channel == "cli":
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=msg.channel, chat_id=msg.chat_id, content="", metadata=msg.metadata or {},
                        ))
                except Exception as e:
                    logger.error("Error processing message: {}", e)
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue

    async def close_mcp(self) -> None:
        """Close MCP connections."""
        if self._mcp_stack:
            try:
                await self._mcp_stack.aclose()
            except (RuntimeError, BaseExceptionGroup):
                pass  # MCP SDK cancel scope cleanup is noisy but harmless
            self._mcp_stack = None

    async def reload_mcp(self, mcp_servers: dict) -> None:
        """Dynamically reload MCP servers."""
        from loguru import logger
        logger.info("Reloading MCP servers...")
        await self.close_mcp()
        
        for name in list(self.tools._tools.keys()):
            if name.startswith("mcp_"):
                self.tools.unregister(name)

        for uctx in self._user_contexts.values():
            for name in list(uctx.tools._tools.keys()):
                if name.startswith("mcp_"):
                    uctx.tools.unregister(name)
                    
        self._mcp_servers = mcp_servers
        self._mcp_connected = False
        self._mcp_connecting = False
        await self._connect_mcp()
        
        if self._mcp_connected:
            for name, tool in self.tools._tools.items():
                if name.startswith("mcp_"):
                    for uctx in self._user_contexts.values():
                        if not uctx.tools.has(name):
                            uctx.tools.register(tool)

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    def _get_consolidation_lock(self, session_key: str) -> asyncio.Lock:
        lock = self._consolidation_locks.get(session_key)
        if lock is None:
            lock = asyncio.Lock()
            self._consolidation_locks[session_key] = lock
        return lock

    def _prune_consolidation_lock(self, session_key: str, lock: asyncio.Lock) -> None:
        """Drop lock entry if no longer in use."""
        if not lock.locked():
            self._consolidation_locks.pop(session_key, None)

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> OutboundMessage | None:
        """Process a single inbound message and return the response."""

        uctx: UserContext | None = None
        if self._repos:
            user_id = await self._resolve_user_id(msg)
            if not user_id:
                return OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id,
                    content="Access denied: unrecognized user. Contact admin for access.",
                )

            if self._rate_limiter:
                rate_err = await self._rate_limiter.check(user_id)
                if rate_err:
                    return OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id, content=rate_err,
                    )

            uctx = await self._get_user_context(user_id)
            if self._rate_limiter:
                self._rate_limiter.record_request(user_id)

        sessions = uctx.sessions if uctx else self.sessions
        context = uctx.context if uctx else self.context
        tools = uctx.tools if uctx else self.tools
        _provider = uctx.provider if uctx and uctx.provider else self.provider
        _model = uctx.model if uctx else self.model
        _max_tokens = uctx.max_tokens if uctx else self.max_tokens
        _temperature = uctx.temperature if uctx else self.temperature
        _max_iterations = uctx.max_iterations if uctx else self.max_iterations
        _memory_window = uctx.memory_window if uctx else self.memory_window
        _memory: MemoryStore | None = uctx.memory if uctx else None

        if msg.channel == "system":
            channel, chat_id = (msg.chat_id.split(":", 1) if ":" in msg.chat_id
                                else ("cli", msg.chat_id))
            logger.info("Processing system message from {}", msg.sender_id)
            key = f"{channel}:{chat_id}"
            session = await sessions.get_or_create(key)
            _user_id = uctx.user_id if uctx else ""
            self._set_tool_context(channel, chat_id, msg.metadata.get("message_id"), tools=tools, user_id=_user_id)
            history = session.get_history(max_messages=_memory_window)
            messages = await context.build_messages(
                history=history,
                current_message=msg.content, channel=channel, chat_id=chat_id,
            )
            final_content, _, all_msgs = await self._run_agent_loop(
                messages, tools=tools, model=_model, temperature=_temperature,
                max_tokens=_max_tokens, max_iterations=_max_iterations,
                provider=_provider,
            )
            self._save_turn(session, all_msgs, 1 + len(history))
            await sessions.save(session)
            return OutboundMessage(channel=channel, chat_id=chat_id,
                                  content=final_content or "Background task completed.")

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)

        key = session_key or msg.session_key
        session = await sessions.get_or_create(key)

        cmd = msg.content.strip().lower()
        if cmd == "/new":
            lock = self._get_consolidation_lock(session.key)
            self._consolidating.add(session.key)
            try:
                async with lock:
                    snapshot = session.messages[session.last_consolidated:]
                    if snapshot:
                        temp = Session(key=session.key)
                        temp.messages = list(snapshot)
                        if not await self._consolidate_memory(temp, archive_all=True, memory=_memory):
                            return OutboundMessage(
                                channel=msg.channel, chat_id=msg.chat_id,
                                content="Memory archival failed, session not cleared. Please try again.",
                            )
            except Exception:
                logger.exception("/new archival failed for {}", session.key)
                return OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id,
                    content="Memory archival failed, session not cleared. Please try again.",
                )
            finally:
                self._consolidating.discard(session.key)
                self._prune_consolidation_lock(session.key, lock)

            session.clear()
            await sessions.save(session)
            sessions.invalidate(session.key)
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="New session started.")
        if cmd == "/help":
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="🐈 nanobot commands:\n/new — Start a new conversation\n/help — Show available commands")

        unconsolidated = len(session.messages) - session.last_consolidated
        if (unconsolidated >= _memory_window and session.key not in self._consolidating):
            self._consolidating.add(session.key)
            lock = self._get_consolidation_lock(session.key)
            _mem = _memory  # capture for closure

            async def _consolidate_and_unlock():
                try:
                    async with lock:
                        await self._consolidate_memory(session, memory=_mem)
                finally:
                    self._consolidating.discard(session.key)
                    self._prune_consolidation_lock(session.key, lock)
                    _task = asyncio.current_task()
                    if _task is not None:
                        self._consolidation_tasks.discard(_task)

            _task = asyncio.create_task(_consolidate_and_unlock())
            self._consolidation_tasks.add(_task)

        _user_id = uctx.user_id if uctx else ""
        self._set_tool_context(msg.channel, msg.chat_id, msg.metadata.get("message_id"), tools=tools, user_id=_user_id)
        if message_tool := tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.start_turn()

        history = session.get_history(max_messages=_memory_window)
        initial_messages = await context.build_messages(
            history=history,
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel, chat_id=msg.chat_id,
        )

        async def _bus_progress(content: str, *, tool_hint: bool = False) -> None:
            meta = dict(msg.metadata or {})
            meta["_progress"] = True
            meta["_tool_hint"] = tool_hint
            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=content, metadata=meta,
            ))

        final_content, _, all_msgs = await self._run_agent_loop(
            initial_messages, on_progress=on_progress or _bus_progress,
            tools=tools, model=_model, temperature=_temperature,
            max_tokens=_max_tokens, max_iterations=_max_iterations,
            provider=_provider,
        )

        if final_content is None:
            final_content = "I've completed processing but have no response to give."

        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)

        self._save_turn(session, all_msgs, 1 + len(history))
        await sessions.save(session)

        if message_tool := tools.get("message"):
            if isinstance(message_tool, MessageTool) and message_tool._sent_in_turn:
                return None

        return OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content=final_content,
            metadata=msg.metadata or {},
        )

    _TOOL_RESULT_MAX_CHARS = 500

    def _save_turn(self, session: Session, messages: list[dict], skip: int) -> None:
        """Save new-turn messages into session, truncating large tool results."""
        from datetime import datetime
        for m in messages[skip:]:
            entry = {k: v for k, v in m.items() if k != "reasoning_content"}
            if entry.get("role") == "tool":
                content = entry.get("content")
                if isinstance(content, list):
                    text_parts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
                    has_images = any(isinstance(b, dict) and b.get("type") == "image_url" for b in content)
                    text = "\n".join(text_parts)
                    if has_images:
                        text += "\n[screenshot]"
                    entry["content"] = text[:self._TOOL_RESULT_MAX_CHARS]
                elif isinstance(content, str) and len(content) > self._TOOL_RESULT_MAX_CHARS:
                    entry["content"] = content[:self._TOOL_RESULT_MAX_CHARS] + "\n... (truncated)"
            entry.setdefault("timestamp", datetime.now().isoformat())
            session.messages.append(entry)
        session.updated_at = datetime.now()

    async def _consolidate_memory(
        self, session: Session, *, archive_all: bool = False,
        memory: MemoryStore | None = None,
    ) -> bool:
        """Delegate to MemoryStore.consolidate(). Returns True on success."""
        _memory = memory or MemoryStore(self.workspace)
        return await _memory.consolidate(
            session, self.provider, self.model,
            archive_all=archive_all, memory_window=self.memory_window,
        )

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        user_id: str | None = None,
    ) -> str:
        """Process a message directly (for CLI or cron usage)."""
        await self._connect_mcp()
        msg = InboundMessage(
            channel=channel, sender_id="user", chat_id=chat_id,
            content=content, user_id=user_id,
        )
        response = await self._process_message(msg, session_key=session_key, on_progress=on_progress)
        return response.content if response else ""
