from agent_commons.base.agent_base import BaseAgent
from typing import Dict, Any, Optional

class SupervisorAgent(BaseAgent):
    """主控Agent"""
    
    async def process_task(self, task: str, context: Optional[Any] = None) -> Dict[str, Any]:
        """处理任务"""
        context = context or {}
        
        relevant_skills = self.get_relevant_skills(task)
        
        # 生成LLM响应
        llm_response = await self.generate_response(task, context)
        
        result = {
            "task": task,
            "skills_used": list(relevant_skills.keys()),
            "status": "processed",
            "message": llm_response
        }
        
        return result
    
    def is_skill_relevant(self, skill_name: str, task: str) -> bool:
        """判断技能是否相关"""
        skill_config = next(
            (s for s in self.config.get("skills", []) if s["name"] == skill_name),
            None
        )
        
        if skill_config:
            keywords = skill_config.get("trigger_keywords", [])
            return any(keyword in task for keyword in keywords)
        
        return False
