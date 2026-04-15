"""
Skill Manager — Framework-level component.

NOT inside any specific skill. This is the orchestration layer that:
1. Scans skills/ directory for available skills (metadata only)
2. Builds a lightweight catalog for the LLM system prompt
3. Loads full SKILL.md on-demand when LLM decides to activate a skill
4. Triggers side-effects (like MCP connections) based on skill type

Key principle: Skills are NEVER auto-loaded. The LLM reads the catalog
and decides when to activate a skill. Only then does the full content
get loaded and any connections get established.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Awaitable

logger = logging.getLogger("framework.skill_manager")


class SkillMetadata:
    """Lightweight metadata for a skill — only name + description."""

    def __init__(self, name: str, description: str, path: Path):
        self.name = name
        self.description = description
        self.path = path  # Path to skill directory
        self.skill_md_path = path / "SKILL.md"

    def __repr__(self):
        return f"<Skill: {self.name}>"


class SkillManager:
    """
    Manages the lifecycle of skills:
    - Registration (scan metadata only)
    - Activation (load full content on LLM request)
    - Deactivation
    
    Does NOT know about MCP specifically. MCP connection is handled
    by the agent when a skill with MCP dependencies is activated.
    """

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._registry: dict[str, SkillMetadata] = {}
        self._active_skills: dict[str, str] = {}  # name -> full content
        self._activation_hooks: dict[str, Callable] = {}  # name -> async callback

    def scan_and_register(self) -> dict[str, SkillMetadata]:
        """
        Scan the skills directory for available skills.
        Only reads YAML frontmatter (name + description).
        Does NOT load full content. Does NOT connect anything.
        
        Returns:
            Registry of skill metadata
        """
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return {}

        for skill_md in sorted(self.skills_dir.rglob("SKILL.md")):
            skill_dir = skill_md.parent

            # Read ONLY the frontmatter (lightweight)
            metadata = self._read_frontmatter(skill_md, skill_dir)
            if metadata:
                self._registry[metadata.name] = metadata
                logger.info(f"📋 Registered skill: {metadata.name} — {metadata.description[:60]}")

        return self._registry

    def register_activation_hook(self, skill_name: str, hook: Callable[["SkillManager", str], Awaitable[Any]]):
        """
        Register an async callback that runs when a skill is activated.
        This is how the agent hooks in MCP connection logic for 'use-mcp'.
        """
        self._activation_hooks[skill_name] = hook

    def build_catalog_prompt(self) -> str:
        """
        Build a lightweight catalog of available skills for the system prompt.
        This is ALL the LLM sees at startup — just names and descriptions.
        
        Returns:
            Formatted string for system prompt injection
        """
        if not self._registry:
            return ""

        lines = [
            "## Available Skills",
            "",
            "You have access to the following skills. Use the `activate_skill` tool ",
            "to load a skill when you need its capabilities. Skills are NOT loaded by default.",
            "",
        ]

        for name, meta in self._registry.items():
            status = "🟢 ACTIVE" if name in self._active_skills else "⚪ available"
            lines.append(f"- **{name}** [{status}]: {meta.description}")

        lines.extend([
            "",
            "To activate a skill, call: `activate_skill(name=\"skill-name\")`",
            "Only activate a skill when the user's request actually needs it.",
        ])

        return "\n".join(lines)

    async def activate_skill(self, name: str) -> dict:
        """
        Load a skill's full SKILL.md content and trigger any activation hooks.
        Called when the LLM decides it needs a skill.
        
        Args:
            name: Skill name from the catalog
            
        Returns:
            { "status": "activated"|"error", "content": str, "side_effects": str }
        """
        if name in self._active_skills:
            return {
                "status": "already_active",
                "content": self._active_skills[name],
                "side_effects": "Skill was already active.",
            }

        if name not in self._registry:
            available = list(self._registry.keys())
            return {
                "status": "error",
                "content": "",
                "side_effects": f"Skill '{name}' not found. Available: {available}",
            }

        meta = self._registry[name]

        # NOW load the full SKILL.md content
        try:
            content = self._read_full_content(meta.skill_md_path)
        except Exception as e:
            return {
                "status": "error",
                "content": "",
                "side_effects": f"Failed to read SKILL.md: {e}",
            }

        self._active_skills[name] = content
        logger.info(f"✅ Activated skill: {name} ({len(content)} chars)")

        # Run activation hook if registered (e.g., connect MCP servers)
        side_effects = "Skill loaded successfully."
        if name in self._activation_hooks:
            try:
                hook_result = await self._activation_hooks[name](self, name)
                if hook_result:
                    side_effects = str(hook_result)
            except Exception as e:
                side_effects = f"Skill loaded but hook failed: {e}"
                logger.error(f"Activation hook error for {name}: {e}")

        return {
            "status": "activated",
            "content": content,
            "side_effects": side_effects,
        }

    async def deactivate_skill(self, name: str) -> str:
        """Remove a skill from active set."""
        if name not in self._active_skills:
            return f"Skill '{name}' is not active."
        del self._active_skills[name]
        logger.info(f"⚪ Deactivated skill: {name}")
        return f"Skill '{name}' deactivated."

    def is_active(self, name: str) -> bool:
        return name in self._active_skills

    def get_active_skills(self) -> list[str]:
        return list(self._active_skills.keys())

    def list_skills(self) -> list[dict]:
        """Return skill catalog as structured data."""
        return [
            {
                "name": name,
                "description": meta.description,
                "active": name in self._active_skills,
            }
            for name, meta in self._registry.items()
        ]

    # ─── Internal helpers ─────────────────────────────────────

    def _read_frontmatter(self, skill_md: Path, skill_dir: Path) -> SkillMetadata | None:
        """Read only YAML frontmatter from SKILL.md — very lightweight."""
        try:
            content = skill_md.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Cannot read {skill_md}: {e}")
            return None

        if not content.startswith("---"):
            return None

        parts = content.split("---", 2)
        if len(parts) < 3:
            return None

        frontmatter = parts[1].strip()

        # Simple YAML parsing (name + description only)
        name = ""
        description = ""
        for line in frontmatter.split("\n"):
            line = line.strip()
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("description:"):
                desc_value = line.split(":", 1)[1].strip()
                if desc_value and desc_value not in (">", "|"):
                    description = desc_value.strip('"').strip("'")
                # For multi-line descriptions, just take the first line
            elif description == "" and not line.startswith(("version", "tags", "triggers", "-", "[")):
                # Continuation of multi-line description
                if line and not any(line.startswith(k) for k in ["name", "version", "tags", "triggers"]):
                    description = line.strip('"').strip("'")

        folder_name = skill_dir.name.replace("_", "-")
        name = name or folder_name

        if not description:
            description = f"Skill: {name}"

        return SkillMetadata(name=name, description=description, path=skill_dir)

    def _read_full_content(self, skill_md: Path) -> str:
        """Read full SKILL.md, stripping YAML frontmatter."""
        content = skill_md.read_text(encoding="utf-8")

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2].strip()

        return content
