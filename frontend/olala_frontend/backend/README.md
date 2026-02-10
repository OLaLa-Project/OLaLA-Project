# OLaLA FastAPI Backend

## Stack
- FastAPI
- PostgreSQL
- Redis (chat event bus)
- Docker Compose

## 1) Start backend infra
```bash
cd backend
docker compose up --build -d
```

## 2) Check health
```bash
curl http://localhost:8000/v1/health
```

## 3) API/WS contracts (Flutter issue_chat)
- `GET /v1/issues/today`
- `GET /v1/chat/messages/{issueId}?limit=50`
- `WS /v1/chat/{issueId}`

WS client events:
- `join`
- `message.create`
- `reaction.toggle`

WS server events:
- `presence`
- `message.ack`
- `message.created`
- `reaction.updated`
- `error`

## 4) Run Flutter with local backend
```bash
flutter run \
  --dart-define=API_BASE=http://localhost:8000/v1 \
  --dart-define=WS_BASE=ws://localhost:8000/v1 \
  --dart-define=PUBLIC_WEB_BASE=https://YOUR_PUBLIC_TUNNEL_DOMAIN
```

## 5) Stop
```bash
docker compose down
```

Data persists in docker volumes:
- `postgres-data`
- `redis-data`
