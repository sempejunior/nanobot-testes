"""Skills loader for agent capabilities."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nanobot.db.repositories import SkillRepository

BUILTIN_SKILLS_DIR = Path(__file__).parent.parent / "skills"


class SkillsLoader:
    """
    Loader for agent skills.

    Skills are markdown files (SKILL.md) that teach the agent how to use
    specific tools or perform certain tasks.

    Supports two modes:
    - Filesystem mode: loads from workspace/skills/ + builtin skills (backward compatible)
    - DB mode: loads from SkillRepository + builtin skills
    """

    def __init__(
        self,
        workspace: Path | None = None,
        *,
        skill_repo: SkillRepository | None = None,
        user_id: str | None = None,
        builtin_skills_dir: Path | None = None,
    ):
        if skill_repo is not None:
            self._mode = "db"
            self._repo = skill_repo
            self._user_id = user_id
        elif workspace is not None:
            self._mode = "fs"
            self.workspace = workspace
            self.workspace_skills = workspace / "skills"
        else:
            raise ValueError("Either workspace or skill_repo must be provided")

        self.builtin_skills = builtin_skills_dir or BUILTIN_SKILLS_DIR

    async def list_skills(self, filter_unavailable: bool = True) -> list[dict[str, str]]:
        """List all available skills."""
        if self._mode == "db":
            return await self._list_skills_db(filter_unavailable)
        return self._list_skills_fs(filter_unavailable)

    async def load_skill(self, name: str) -> str | None:
        """Load a skill by name."""
        if self._mode == "db":
            skill = await self._repo.get_skill(self._user_id, name)
            if skill:
                return skill["content"]
        else:
            workspace_skill = self.workspace_skills / name / "SKILL.md"
            if workspace_skill.exists():
                return workspace_skill.read_text(encoding="utf-8")

        if self.builtin_skills:
            builtin_skill = self.builtin_skills / name / "SKILL.md"
            if builtin_skill.exists():
                return builtin_skill.read_text(encoding="utf-8")
        return None

    async def load_skills_for_context(self, skill_names: list[str]) -> str:
        """Load specific skills for inclusion in agent context."""
        parts = []
        for name in skill_names:
            content = await self.load_skill(name)
            if content:
                content = self._strip_frontmatter(content)
                parts.append(f"### Skill: {name}\n\n{content}")
        return "\n\n---\n\n".join(parts) if parts else ""

    async def build_skills_summary(self) -> str:
        """Build a summary of all skills (name, description, availability)."""
        all_skills = await self.list_skills(filter_unavailable=False)
        if not all_skills:
            return ""

        def escape_xml(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        lines = ["<skills>"]
        for s in all_skills:
            name = escape_xml(s["name"])
            path = s.get("path", "")
            desc = escape_xml(await self._get_skill_description(s["name"]))
            skill_meta = await self._get_skill_meta(s["name"])
            available = self._check_requirements(skill_meta)

            lines.append(f'  <skill available="{str(available).lower()}">')
            lines.append(f"    <name>{name}</name>")
            lines.append(f"    <description>{desc}</description>")
            if path:
                lines.append(f"    <location>{path}</location>")

            if not available:
                missing = self._get_missing_requirements(skill_meta)
                if missing:
                    lines.append(f"    <requires>{escape_xml(missing)}</requires>")

            lines.append("  </skill>")
        lines.append("</skills>")

        return "\n".join(lines)

    async def get_always_skills(self) -> list[str]:
        """Get skills marked as always=true that meet requirements."""
        result = []
        for s in await self.list_skills(filter_unavailable=True):
            meta = await self.get_skill_metadata(s["name"]) or {}
            skill_meta = self._parse_nanobot_metadata(meta.get("metadata", ""))
            if skill_meta.get("always") or meta.get("always"):
                result.append(s["name"])
        return result

    async def get_skill_metadata(self, name: str) -> dict | None:
        """Get metadata from a skill's frontmatter."""
        content = await self.load_skill(name)
        if not content:
            return None

        if content.startswith("---"):
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if match:
                metadata = {}
                for line in match.group(1).split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip().strip("\"'")
                return metadata
        return None

    async def _list_skills_db(self, filter_unavailable: bool) -> list[dict[str, str]]:
        """List skills: DB user skills + filesystem builtin skills."""
        skills = []

        db_skills = await self._repo.list_skills(self._user_id)
        for s in db_skills:
            skills.append({
                "name": s["name"],
                "source": "user",
                "content": s.get("content", ""),
            })

        user_names = {s["name"] for s in skills}
        if self.builtin_skills and self.builtin_skills.exists():
            for skill_dir in self.builtin_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists() and skill_dir.name not in user_names:
                        skills.append({
                            "name": skill_dir.name,
                            "path": str(skill_file),
                            "source": "builtin",
                        })

        if filter_unavailable:
            filtered = []
            for s in skills:
                meta = await self._get_skill_meta(s["name"])
                if self._check_requirements(meta):
                    filtered.append(s)
            return filtered
        return skills

    def _list_skills_fs(self, filter_unavailable: bool) -> list[dict[str, str]]:
        """List skills from workspace + builtin directories (sync)."""
        skills = []

        if self.workspace_skills.exists():
            for skill_dir in self.workspace_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        skills.append({"name": skill_dir.name, "path": str(skill_file), "source": "workspace"})

        if self.builtin_skills and self.builtin_skills.exists():
            for skill_dir in self.builtin_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists() and not any(s["name"] == skill_dir.name for s in skills):
                        skills.append({"name": skill_dir.name, "path": str(skill_file), "source": "builtin"})

        if filter_unavailable:
            return [s for s in skills if self._check_requirements(self._get_skill_meta_sync(s["name"]))]
        return skills

    def _strip_frontmatter(self, content: str) -> str:
        """Remove YAML frontmatter from markdown content."""
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end():].strip()
        return content

    def _parse_nanobot_metadata(self, raw: str) -> dict:
        """Parse skill metadata JSON from frontmatter."""
        try:
            data = json.loads(raw)
            return data.get("nanobot", data.get("openclaw", {})) if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def _check_requirements(self, skill_meta: dict) -> bool:
        """Check if skill requirements are met (bins, env vars)."""
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                return False
        for env in requires.get("env", []):
            if not os.environ.get(env):
                return False
        return True

    def _get_missing_requirements(self, skill_meta: dict) -> str:
        missing = []
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                missing.append(f"CLI: {b}")
        for env in requires.get("env", []):
            if not os.environ.get(env):
                missing.append(f"ENV: {env}")
        return ", ".join(missing)

    async def _get_skill_description(self, name: str) -> str:
        """Get the description of a skill from its frontmatter."""
        meta = await self.get_skill_metadata(name)
        if meta and meta.get("description"):
            return meta["description"]
        return name

    async def _get_skill_meta(self, name: str) -> dict:
        """Get nanobot metadata for a skill (async, works in both modes)."""
        meta = await self.get_skill_metadata(name) or {}
        return self._parse_nanobot_metadata(meta.get("metadata", ""))

    def _get_skill_meta_sync(self, name: str) -> dict:
        """Get nanobot metadata for a skill (sync, filesystem mode only)."""
        content = None
        workspace_skill = self.workspace_skills / name / "SKILL.md"
        if workspace_skill.exists():
            content = workspace_skill.read_text(encoding="utf-8")
        elif self.builtin_skills:
            builtin_skill = self.builtin_skills / name / "SKILL.md"
            if builtin_skill.exists():
                content = builtin_skill.read_text(encoding="utf-8")

        if not content:
            return {}

        if content.startswith("---"):
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if match:
                metadata = {}
                for line in match.group(1).split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip().strip("\"'")
                return self._parse_nanobot_metadata(metadata.get("metadata", ""))
        return {}
