import frontmatter
from pathlib import Path
from typing import Dict, Any
from langchain_core.tools import tool


def _get_skills_dir() -> Path:
    base_dir = Path(__file__).resolve().parent.parent.parent
    return base_dir / "supervisor_agent" / "skills"


@tool("read_skill_content")
def read_skill_content(skill_name: str) -> Dict[str, Any]:
    """
    Read the full content of a skill's SKILL.md file.

    Use this tool when you need detailed instructions, scripts, references, or any content
    from a specific skill. First, check available skills from the system prompt metadata,
    then use this tool to load the full skill content when needed.

    Args:
        skill_name: Name of the skill as defined in SKILL.md frontmatter (e.g., "MySQL Executor Skill", "skill-creator").

    Returns:
        Dict with fields:
        - success (bool): Whether the skill was found and loaded.
        - name (str): Skill name from metadata.
        - description (str): Skill description from metadata.
        - content (str): Full markdown content of SKILL.md.
        - error (str, optional): Error message if loading failed.
    """
    skills_dir = _get_skills_dir()

    if not skills_dir.exists():
        return {
            "success": False,
            "error": "Skills directory not found"
        }

    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        try:
            post = frontmatter.load(skill_file)
            name = post.metadata.get('name', skill_dir.name)
            if name == skill_name:
                return {
                    "success": True,
                    "name": name,
                    "description": post.metadata.get('description', ''),
                    "content": post.content
                }
        except Exception:
            continue

    available = [f.name for f in skills_dir.iterdir() if f.is_dir() and (f / "SKILL.md").exists()]
    return {
        "success": False,
        "error": f"Skill not found: '{skill_name}'. Available skills: {available}"
    }


tools = [
    read_skill_content,
]
