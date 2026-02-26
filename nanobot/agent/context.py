"""Context builder for assembling agent prompts."""

from __future__ import annotations

import base64
import mimetypes
import os
import platform
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nanobot.agent.memory import MemoryStore
from nanobot.agent.skills import SkillsLoader

if TYPE_CHECKING:
    from nanobot.db.repositories import MemoryRepository, SkillRepository, UserRepository


class ContextBuilder:
    """
    Builds the context (system prompt + messages) for the agent.

    Assembles bootstrap files, memory, skills, and conversation history
    into a coherent prompt for the LLM.

    Supports two modes:
    - **Filesystem (fs)**: reads bootstrap files from workspace directory (default).
    - **Database (db)**: reads bootstrap files from user's record in the DB,
      falling back to workspace files for any missing entries.
    """

    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md"]

    def __init__(
        self,
        workspace: Path,
        *,
        memory_store: MemoryStore | None = None,
        skills_loader: SkillsLoader | None = None,
        user_repo: "UserRepository | None" = None,
        user_id: str | None = None,
        language: str = "",
        custom_instructions: str = "",
    ):
        self.workspace = workspace
        self.memory = memory_store or MemoryStore(workspace)
        self.skills = skills_loader or SkillsLoader(workspace)
        self._user_repo = user_repo
        self._user_id = user_id
        self._language = language
        self._custom_instructions = custom_instructions
        self._mode: str = "db" if user_repo is not None and user_id is not None else "fs"

    async def build_system_prompt(self, skill_names: list[str] | None = None) -> str:
        """
        Build the system prompt from bootstrap files, memory, and skills.

        Args:
            skill_names: Optional list of skills to include.

        Returns:
            Complete system prompt.
        """
        parts = []

        parts.append(self._get_identity())

        bootstrap = await self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)

        memory = await self.memory.get_memory_context()
        if memory:
            parts.append(f"# Memory\n\n{memory}")

        always_skills = await self.skills.get_always_skills()
        if always_skills:
            always_content = await self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")

        skills_summary = await self.skills.build_skills_summary()
        if skills_summary:
            parts.append(f"""# Skills

The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
Skills with available="false" need dependencies installed first - you can try installing them with apt/brew.

{skills_summary}""")

        return "\n\n---\n\n".join(parts)

    def _get_desktop_section(self) -> str:
        """Return desktop environment section if a display is available."""
        display = os.environ.get("DISPLAY")
        if not display:
            return ""
        chromium_path = os.environ.get("PUPPETEER_EXECUTABLE_PATH", "/usr/bin/chromium")
        return f"""

## Desktop Environment
Display {display} (1280x720). Chromium browser at `{chromium_path}`.
VNC on port 5900, noVNC on port 6080.

### Tools
- `screenshot` — capture the screen (always available). Options: `grid=true` for coordinate overlay, `ocr=true` for text extraction.
- `computer` — click, type, scroll, key press, `wait`, `window_info`.
- `browser` — execute JavaScript in the active browser tab via CDP. Read DOM, fill forms, click by selector, get URLs. Much faster than visual clicking for web pages.
- `exec` — launch applications, e.g. `chromium --no-sandbox --display={display} "<url>"`

### Web Navigation Workflow
1. Navigate: `browser(code="window.location.href", url="https://example.com")`
2. Read page: `browser(code="document.title")` or `browser(code="document.body.innerText")`
3. Fill forms: `browser(code="document.querySelector('#email').value = 'user@test.com'")`
4. Click elements: `browser(code="document.querySelector('button.submit').click()")`
5. Use `screenshot` to visually verify the result when needed
6. For non-browser desktop apps, use `computer` actions (click, type, key)

IMPORTANT: Always use `--no-sandbox` with Chromium (required in container)."""

    def _get_identity(self) -> str:
        """Get the core identity section."""
        from datetime import datetime
        import time as _time
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = _time.strftime("%Z") or "UTC"
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"
        desktop = self._get_desktop_section()

        if self._mode == "db":
            return f"""# nanobot

You are nanobot, a helpful AI assistant.

## Current Time
{now} ({tz})

## Runtime
{runtime}

## Workspace
Your workspace is at: {workspace_path}

Reply directly with text for conversations. Only use the 'message' tool to send to a specific chat channel.

## Tool Call Guidelines
- Before calling tools, you may briefly state your intent (e.g. "Let me check that"), but NEVER predict or describe the expected result before receiving it.
- Before modifying a file, read it first to confirm its current content.
- Do not assume a file or directory exists — use list_dir or read_file to verify.
- After writing or editing a file, re-read it if accuracy matters.
- If a tool call fails, analyze the error before retrying with a different approach.

## Memory
- **Proactively save** important facts with the `save_memory` tool — don't wait to be asked.
  Save things like: user's name, preferences, project details, technical decisions, tasks discussed, things the user asked you to remember.
- Use `search_memory` to recall past conversations before asking the user to repeat themselves.
- Old conversations are automatically consolidated when the session grows large.
- Do NOT use edit_file or write_file on memory files. Always use the memory tools.{desktop}{self._get_user_settings_section()}"""

        return f"""# nanobot 🐈

You are nanobot, a helpful AI assistant.

## Current Time
{now} ({tz})

## Runtime
{runtime}

## Workspace
Your workspace is at: {workspace_path}
- Long-term memory: {workspace_path}/memory/MEMORY.md
- History log: {workspace_path}/memory/HISTORY.md (grep-searchable)
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md

Reply directly with text for conversations. Only use the 'message' tool to send to a specific chat channel.

## Tool Call Guidelines
- Before calling tools, you may briefly state your intent (e.g. "Let me check that"), but NEVER predict or describe the expected result before receiving it.
- Before modifying a file, read it first to confirm its current content.
- Do not assume a file or directory exists — use list_dir or read_file to verify.
- After writing or editing a file, re-read it if accuracy matters.
- If a tool call fails, analyze the error before retrying with a different approach.

## Memory
- Remember important facts: write to {workspace_path}/memory/MEMORY.md
- Recall past events: grep {workspace_path}/memory/HISTORY.md{desktop}"""

    def _get_user_settings_section(self) -> str:
        """Build optional sections from user settings (language, custom instructions)."""
        parts = []
        if self._language:
            parts.append(f"\n\n## Language\nAlways respond in {self._language}.")
        if self._custom_instructions:
            parts.append(f"\n\n## User Instructions\n{self._custom_instructions}")
        return "".join(parts)

    async def _load_bootstrap_files(self) -> str:
        """Load bootstrap files from DB (with filesystem fallback) or filesystem only."""
        if self._mode == "db":
            return await self._load_bootstrap_db()
        return self._load_bootstrap_fs()

    async def _load_bootstrap_db(self) -> str:
        """Load bootstrap from user's DB record, falling back to workspace files."""
        user_bootstrap: dict[str, str] = {}
        if self._user_repo and self._user_id:
            user = await self._user_repo.get_by_id(self._user_id)
            if user:
                user_bootstrap = user.get("bootstrap", {})

        parts = []
        for filename in self.BOOTSTRAP_FILES:
            content = user_bootstrap.get(filename)
            if not content:
                file_path = self.workspace / filename
                if file_path.exists():
                    content = file_path.read_text(encoding="utf-8")
            if content:
                parts.append(f"## {filename}\n\n{content}")

        return "\n\n".join(parts) if parts else ""

    def _load_bootstrap_fs(self) -> str:
        """Load all bootstrap files from workspace (filesystem mode)."""
        parts = []

        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")

        return "\n\n".join(parts) if parts else ""

    async def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build the complete message list for an LLM call.

        Args:
            history: Previous conversation messages.
            current_message: The new user message.
            skill_names: Optional skills to include.
            media: Optional list of local file paths for images/media.
            channel: Current channel (telegram, feishu, etc.).
            chat_id: Current chat/user ID.

        Returns:
            List of messages including system prompt.
        """
        messages = []

        system_prompt = await self.build_system_prompt(skill_names)
        if channel and chat_id:
            system_prompt += f"\n\n## Current Session\nChannel: {channel}\nChat ID: {chat_id}"
        messages.append({"role": "system", "content": system_prompt})

        messages.extend(history)

        user_content = self._build_user_content(current_message, media)
        messages.append({"role": "user", "content": user_content})

        return messages

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        """Build user message content with optional base64-encoded images."""
        if not media:
            return text

        images = []
        for path in media:
            p = Path(path)
            mime, _ = mimetypes.guess_type(path)
            if not p.is_file() or not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(p.read_bytes()).decode()
            images.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})

        if not images:
            return text
        return images + [{"type": "text", "text": text}]

    def add_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str | list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Add a tool result to the message list."""
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result,
        })
        return messages

    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        reasoning_content: str | None = None,
    ) -> list[dict[str, Any]]:
        """Add an assistant message to the message list."""
        msg: dict[str, Any] = {"role": "assistant"}
        msg["content"] = content

        if tool_calls:
            msg["tool_calls"] = tool_calls

        if reasoning_content is not None:
            msg["reasoning_content"] = reasoning_content

        messages.append(msg)
        return messages
