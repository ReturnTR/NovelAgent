from pydantic import BaseModel, Field
from typing import Any, Optional, Dict
from enum import Enum

class MessageType(str, Enum):
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    TASK_PROGRESS = "task_progress"
    AGENT_DISCOVERY = "agent_discovery"
    HEARTBEAT = "heartbeat"
    ERROR = "error"

class A2AMessage(BaseModel):
    message_id: str
    message_type: MessageType
    sender: str
    receiver: Optional[str] = None
    task_id: Optional[str] = None
    timestamp: str
    content: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "msg-001",
                "message_type": "task_request",
                "sender": "supervisor-001",
                "receiver": "character-001",
                "task_id": "task-001",
                "timestamp": "2024-04-13T10:00:00Z",
                "content": {
                    "capability": "create_character",
                    "params": {
                        "novel_id": 1,
                        "requirements": "创建一个勇敢的男主角"
                    }
                }
            }
        }
