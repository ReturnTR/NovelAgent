from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class AgentCapability(BaseModel):
    name: str
    description: str
    parameters: Dict[str, str]

class AgentIdentity(BaseModel):
    agent_id: str
    agent_name: str
    agent_type: str
    endpoint: str
    version: str
    capabilities: List[AgentCapability] = []
    status: str = "active"
    created_at: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "character-001",
                "agent_name": "Character Agent",
                "agent_type": "character",
                "endpoint": "http://localhost:8002",
                "version": "1.0.0",
                "capabilities": [
                    {
                        "name": "create_character",
                        "description": "创建新人物",
                        "parameters": {
                            "novel_id": "小说ID",
                            "character_data": "人物数据JSON"
                        }
                    }
                ],
                "status": "active",
                "created_at": "2024-04-13T00:00:00Z"
            }
        }
