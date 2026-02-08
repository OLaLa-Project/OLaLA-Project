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

COMPOSE_FILE="infra/docker/docker-compose.beta.yml"
POSTGRES_DB="${POSTGRES_DB:-olala}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
OLLAMA_URL="${OLLAMA_URL:-http://ollama:11434}"
START_OLLAMA="${OLALA_START_OLLAMA:-0}"

if [ "${1:-}" = "--with-ollama" ]; then
  START_OLLAMA=1
  shift
elif [ "${1:-}" = "--without-ollama" ]; then
  START_OLLAMA=0
  shift
fi

echo "[1/4] backend/wiki-db 상태 보장"
docker compose -f "$COMPOSE_FILE" up -d wiki-db backend >/dev/null

if [ "$START_OLLAMA" = "1" ]; then
  if [[ "$OLLAMA_URL" == http://ollama:11434* ]]; then
    echo "[2/4] ollama profile 서비스 기동 (opt-in)"
    COMPOSE_PROFILES=llm docker compose -f "$COMPOSE_FILE" up -d ollama >/dev/null
  else
    echo "[2/4] OLLAMA_URL=$OLLAMA_URL (내부 ollama 자동기동 생략)"
  fi
else
  echo "[2/4] ollama 자동기동 비활성화 (필요 시 OLALA_START_OLLAMA=1 또는 --with-ollama)"
fi

echo "[3/4] backfill 전 임베딩 현황"
docker compose -f "$COMPOSE_FILE" exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS embedded, COUNT(*) FILTER (WHERE embedding IS NULL) AS missing, COUNT(*) AS total FROM public.wiki_chunks;"

echo "[4/4] backfill 실행"
docker compose -f "$COMPOSE_FILE" exec -T backend python -m app.tools.wiki_embeddings_backfill "$@"
