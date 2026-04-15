from agent.core.base.agent_base import BaseAgent
from typing import Dict, Any, Optional

class CharacterAgent(BaseAgent):
    """人物生成Agent"""

    def is_skill_relevant(self, skill_name: str, task: str) -> bool:
        skill_config = next(
            (s for s in self.config.get("skills", []) if s["name"] == skill_name),
            None
        )

        if skill_config:
            keywords = skill_config.get("trigger_keywords", [])
            return any(keyword in task for keyword in keywords)

        return False
