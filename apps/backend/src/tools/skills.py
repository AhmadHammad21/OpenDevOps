"""Skills registry — auto-discovers SKILL.md files under src/skills/.

Two tools are exposed to the agent:
  list_skills()      — returns names + descriptions of all available skills
  use_skill(name)    — loads the full investigation steps for a named skill

The agent should call use_skill() for whichever skill matches the incident type.
Available skill names and descriptions are already injected into the system prompt,
so list_skills() is only needed if the agent wants to refresh or confirm what exists.
Full content is loaded on demand so unrelated skills cost zero tokens.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_SKILLS_DIR = Path(__file__).parent.parent / "skills"
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---[ \t]*\n?", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    result: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            result[key.strip()] = val.strip()
    return result


@lru_cache(maxsize=1)
def _load_registry() -> dict[str, dict[str, str]]:
    """Scan skills dir once and cache {name: {description, content}}."""
    registry: dict[str, dict[str, str]] = {}
    if not _SKILLS_DIR.exists():
        return registry
    for skill_path in sorted(_SKILLS_DIR.glob("*/SKILL.md")):
        text = skill_path.read_text(encoding="utf-8")
        meta = _parse_frontmatter(text)
        slug = skill_path.parent.name
        name = meta.get("name") or slug
        description = meta.get("description", "")
        body = _FRONTMATTER_RE.sub("", text).strip()
        registry[name] = {"slug": slug, "description": description, "content": body}
    return registry


def available_skill_summaries() -> list[dict[str, str]]:
    """Return [{name, description}] for all discovered skills (no full content)."""
    return [
        {"name": name, "description": info["description"]}
        for name, info in _load_registry().items()
    ]


def list_skills() -> dict:
    """List all available investigation skills with their names and descriptions."""
    items = available_skill_summaries()
    return {"skills": items, "count": len(items)}


def use_skill(name: str) -> dict:
    """Load the full investigation skill for a named incident type.
    The skill contains step-by-step investigation guidance, key metrics to check,
    log patterns to look for, and common root causes with mitigations."""
    registry = _load_registry()
    if name not in registry:
        return {
            "error": f"Skill '{name}' not found.",
            "available": list(registry.keys()),
        }
    return {"name": name, "skill": registry[name]["content"]}


ALL_SKILL_TOOLS = [list_skills, use_skill]
