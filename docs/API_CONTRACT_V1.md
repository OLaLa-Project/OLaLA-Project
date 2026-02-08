# API Contract V1 (Flutter 안정성 우선)

## Base
- REST: `{API_BASE}` (예: `http://127.0.0.1:8080/v1`)
- WS: `{WS_BASE}` (예: `ws://127.0.0.1:8080/v1`)

## 1) 오늘의 이슈
- `GET /v1/issues/today`
- Response:
```json
{
  "id": "issue_20260207",
  "title": "string",
  "summary": "string",
  "content": "string",
  "category": "string",
  "participantCount": 0,
  "publishedAt": "2026-02-07T00:00:00Z"
}
```

## 2) 채팅 히스토리
- `GET /v1/chat/messages/{issueId}?limit=50`
- Response: `ChatMessage[]`

## 3) 채팅 WebSocket
- `GET /v1/chat/{issueId}` (WebSocket)

### Client -> Server
- `join`
- `message.create`
- `reaction.toggle`

### Server -> Client
- `message.ack`
- `message.created`
- `reaction.updated`
- `presence`
- `error`

## 4) 팩트체크
- `POST /truth/check` (기존 백엔드 표준)
- Flutter 어댑터에서 `VerificationResult`로 매핑
