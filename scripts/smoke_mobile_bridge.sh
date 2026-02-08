#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env.beta ]; then
  echo "[error] .env.beta 파일이 없습니다. cp .env.example .env.beta 후 다시 실행하세요."
  exit 1
fi

# shellcheck disable=SC1091
source .env.beta

BACKEND_PORT="${BACKEND_PORT:-8080}"
BASE_URL="${1:-http://127.0.0.1:${BACKEND_PORT}}"

echo "[1/4] health check"
HEALTH_JSON="$(curl -fsS "$BASE_URL/health")"
echo "$HEALTH_JSON"

echo "[2/4] issue endpoint check"
ISSUE_JSON="$(curl -fsS "$BASE_URL/v1/issues/today")"
echo "$ISSUE_JSON" | sed -n '1,1p'

ISSUE_ID="$(echo "$ISSUE_JSON" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')"
if [ -z "$ISSUE_ID" ]; then
  echo "[error] issue id parse failed"
  exit 1
fi
echo "[info] issue_id=$ISSUE_ID"

echo "[3/4] chat history endpoint check"
CHAT_JSON="$(curl -fsS "$BASE_URL/v1/chat/messages/$ISSUE_ID?limit=5")"
echo "$CHAT_JSON" | sed -n '1,1p'

echo "[4/4] truth check endpoint availability"
STATUS_CODE="$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/truth/check" || true)"
if [ "$STATUS_CODE" = "405" ] || [ "$STATUS_CODE" = "422" ] || [ "$STATUS_CODE" = "200" ]; then
  echo "[ok] /truth/check reachable (status=$STATUS_CODE)"
else
  echo "[warn] /truth/check unexpected status=$STATUS_CODE"
fi

echo "[ok] mobile bridge smoke test passed"
