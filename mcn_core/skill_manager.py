"""Utilities for building temporary skill files."""
import json
from pathlib import Path
from typing import Dict, Any, Optional


class SkillBuilder:
    """Creates simple skill markdown files for loop CLI."""

    def create_temp_skill_file(self, skills_data: Dict[str, Any], workspace_dir: Path) -> str:
        workspace_dir.mkdir(parents=True, exist_ok=True)
        skill_file = workspace_dir / "skill_dynamic.md"
        content = self._render(skills_data)
        skill_file.write_text(content, encoding="utf-8")
        return skill_file.resolve().as_uri()

    def _render(self, skills_data: Dict[str, Any]) -> str:
        selected = skills_data.get("selected_skills") or []
        enabled_categories = skills_data.get("enabled_categories") or []
        skill_names = skills_data.get("skill_names") or []

        return "\n".join([
            "# Auto-Generated Skill File",
            "",
            "## Selected Skills",
            json.dumps(selected, ensure_ascii=False, indent=2),
            "",
            "## Enabled Categories",
            json.dumps(enabled_categories, ensure_ascii=False, indent=2),
            "",
            "## Skill Names",
            json.dumps(skill_names, ensure_ascii=False, indent=2),
        ])


_builder: Optional[SkillBuilder] = None


def get_skill_builder() -> SkillBuilder:
    """Return singleton skill builder."""
    global _builder
    if _builder is None:
        _builder = SkillBuilder()
    return _builder
