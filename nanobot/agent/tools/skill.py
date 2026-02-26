"""Tools for managing agent skills."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool


class SaveSkillTool(Tool):
    """
    Tool to save a learned skill as markdown documentation.
    
    This writes a Markdown file with YAML frontmatter containing 'name'
    and 'description', followed by the instructional content.
    """

    def __init__(
        self,
        *,
        workspace: Path | None = None,
        skill_repo: Any | None = None,
        user_id: str | None = None,
    ):
        self.workspace = workspace
        self.skill_repo = skill_repo
        self.user_id = user_id
        if not workspace and not (skill_repo and user_id):
            raise ValueError("Must provide either workspace or (skill_repo + user_id)")

    @property
    def name(self) -> str:
        return "save_skill"

    @property
    def description(self) -> str:
        return (
            "Save or update a procedural skill. Use this when the user instructs you "
            "to 'learn' or 'remember' a workflow, or when you write tools/scripts you want to keep. "
            "The content MUST be markdown with a YAML frontmatter block containing 'name' and 'description'."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Short, hyphen-separated name (e.g., 'deploy-app').",
                    "maxLength": 64,
                },
                "skill_description": {
                    "type": "string",
                    "description": "Brief explanation of when to trigger this skill.",
                    "maxLength": 255,
                },
                "skill_content": {
                    "type": "string",
                    "description": "The full Markdown content including the procedural instructions. Do NOT include the YAML frontmatter in this string, it will be added automatically.",
                },
            },
            "required": ["skill_name", "skill_description", "skill_content"],
        }

    async def execute(self, **kwargs: Any) -> str:
        name = kwargs.get("skill_name", "").strip().lower()
        desc = kwargs.get("skill_description", "").strip()
        content = kwargs.get("skill_content", "").strip()

        if not name or not desc or not content:
            return "Error: skill_name, skill_description, and skill_content are required."

        full_markdown = f"---\nname: {name}\ndescription: {desc}\n---\n\n{content}"

        if self.skill_repo and self.user_id:
            await self.skill_repo.save_skill(
                self.user_id,
                {
                    "name": name,
                    "description": desc,
                    "content": full_markdown,
                }
            )
            return f"Skill '{name}' successfully saved to database."
        elif self.workspace:
            skill_dir = self.workspace / "skills" / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(full_markdown, encoding="utf-8")
            return f"Skill '{name}' successfully saved to filesystem at {skill_file}."
        
        return "Error: No storage configured for skills."
