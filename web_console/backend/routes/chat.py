"""Chat streaming routes"""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter(tags=["chat"])


class ChatMessage(BaseModel):
    message: str
    agent_id: str


@router.post("/chat/stream")
async def chat_stream(request: Request, chat_message: ChatMessage):
    if not chat_message.agent_id:
        import json
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': 'agent_id is required'}, ensure_ascii=False)}\n\n"]),
            media_type="text/event-stream"
        )

    agent_service = request.app.state.agent_service
    try:
        return await agent_service.chat_stream(chat_message.agent_id, chat_message.message)
    except ValueError as e:
        import json
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"]),
            media_type="text/event-stream"
        )