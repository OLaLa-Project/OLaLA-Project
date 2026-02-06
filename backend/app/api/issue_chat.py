
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Models ---

class DailyIssue(BaseModel):
    id: str
    title: str
    summary: str
    imageUrl: str | None = None
    date: str

class ChatMessage(BaseModel):
    id: str
    userId: str
    username: str
    content: str
    timestamp: str
    reactionCount: int = 0
    isReactedByMe: bool = False

# --- Mock Data ---

MOCK_ISSUE = DailyIssue(
    id="issue_20240206",
    title="GPT-5.3 코덱스, 개발자 직군 대체 가속화 논란",
    summary="최근 발표된 GPT-5.3 코덱스가 기존 5.2 버전에 비해 코딩 성능이 비약적으로 향상되었다는 주장이 제기되었습니다.",
    date="2026-02-06",
    imageUrl=None
)

MOCK_MESSAGES: Dict[str, List[ChatMessage]] = {
    "issue_20240206": [
        ChatMessage(
            id="msg_1",
            userId="user_1",
            username="TechGuru",
            content="5.3 써봤는데 진짜 다르긴 하더라.",
            timestamp=datetime.now().isoformat(),
            reactionCount=5
        ),
         ChatMessage(
            id="msg_2",
            userId="user_2",
            username="DevJunior",
            content="결국 우리 다 짤리는 건가요? ㅠㅠ",
            timestamp=datetime.now().isoformat(),
            reactionCount=2
        )
    ]
}

# --- Connection Manager ---

class ConnectionManager:
    def __init__(self):
        # issue_id -> List[WebSocket]
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, issue_id: str):
        await websocket.accept()
        if issue_id not in self.active_connections:
            self.active_connections[issue_id] = []
        self.active_connections[issue_id].append(websocket)

    def disconnect(self, websocket: WebSocket, issue_id: str):
        if issue_id in self.active_connections:
            if websocket in self.active_connections[issue_id]:
                self.active_connections[issue_id].remove(websocket)

    async def broadcast(self, message: dict, issue_id: str):
        if issue_id in self.active_connections:
            # Clone list to avoid modification during iteration issues
            for connection in list(self.active_connections[issue_id]):
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message: {e}")
                    # Could remove dead connection here

manager = ConnectionManager()

# --- Endpoints ---

@router.get("/issues/today", response_model=DailyIssue)
async def get_today_issue():
    # In a real app, fetch from DB based on date
    return MOCK_ISSUE

@router.get("/chat/messages/{issue_id}", response_model=List[ChatMessage])
async def get_chat_history(issue_id: str, limit: int = 50):
    messages = MOCK_MESSAGES.get(issue_id, [])
    return messages[-limit:]

@router.websocket("/ws/issues/{issue_id}/chat")
async def websocket_endpoint(websocket: WebSocket, issue_id: str):
    await manager.connect(websocket, issue_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Expecting JSON payload from client
            try:
                payload = json.loads(data)
                event_type = payload.get("type")
                
                # Simple Echo / Broadcast logic for MVP
                # Real app would process message, save to DB, then broadcast
                
                if event_type == "message.create":
                    # Broadcast receiving message
                    out_msg = {
                        "type": "message.created",
                        "issueId": issue_id,
                        "message": {
                            "id": f"server_{datetime.now().timestamp()}",
                            "userId": payload.get("userId"),
                            "username": payload.get("nickname"),
                            "content": payload.get("content"),
                            "timestamp": datetime.now().isoformat(),
                            "reactionCount": 0,
                            "isReactedByMe": False,
                            "clientId": payload.get("clientId") # Echo back for ack
                        },
                        "clientId": payload.get("clientId")
                    }
                    await manager.broadcast(out_msg, issue_id)
                
                elif event_type == "reaction.toggle":
                    # Broadcast reaction update
                    out_msg = {
                        "type": "reaction.updated",
                        "issueId": issue_id,
                        "messageId": payload.get("messageId"),
                        "count": 99, # Mock count update
                        "isReactedByMe": True # Mock toggle
                    }
                    await manager.broadcast(out_msg, issue_id)

            except json.JSONDecodeError:
                logger.error("Invalid JSON received over WS")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, issue_id)
