# olala_frontend

A new Flutter project.

## FastAPI Backend (issue_chat)

Local backend infra for `issue_chat` is available in `backend`.

### 1) Start backend infra

```bash
cd backend
docker compose up --build -d
```

### 2) Run Flutter against local backend

```bash
flutter run \
  --dart-define=API_BASE=http://localhost:8000/v1 \
  --dart-define=WS_BASE=ws://localhost:8000/v1
```

For demo QR(web participation from real phones), add:

```bash
--dart-define=PUBLIC_WEB_BASE=https://YOUR_PUBLIC_TUNNEL_DOMAIN
```

### 3) Backend details

See `backend/README.md`.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.
