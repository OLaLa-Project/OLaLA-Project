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
TRUTH_TIMEOUT_SECONDS="${TRUTH_TIMEOUT_SECONDS:-240}"

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

echo "[4/4] truth check functional check"
if ! TRUTH_JSON="$(curl -fsS --max-time "$TRUTH_TIMEOUT_SECONDS" -X POST "$BASE_URL/v1/truth/check" \
  -H 'Content-Type: application/json' \
  -d '{"input_type":"text","input_payload":"지구는 태양을 돈다","language":"ko","include_full_outputs":false}')"; then
  echo "[error] truth/check 호출 실패 또는 타임아웃(${TRUTH_TIMEOUT_SECONDS}s)"
  exit 1
fi
echo "$TRUTH_JSON" | sed -n '1,1p'

if ! echo "$TRUTH_JSON" | grep -q '"analysis_id"'; then
  echo "[error] truth/check 응답에 analysis_id가 없습니다."
  exit 1
fi

if echo "$TRUTH_JSON" | grep -Eq '"(LLM_JUDGE_FAILED|PIPELINE_CRASH|QUALITY_GATE_FAILED|PERSISTENCE_FAILED)"'; then
  echo "[warn] truth/check는 응답했지만 핵심 리스크 플래그가 감지되었습니다."
  echo "[warn] 백엔드 모델 연결/DB 저장 상태를 점검하세요."
  exit 1
fi

echo "[ok] mobile bridge smoke test passed"
