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
STOP_FILE="${1:-${EMBED_STOP_FILE:-/tmp/wiki-embed.stop}}"

docker compose -f "$COMPOSE_FILE" up -d backend >/dev/null
docker compose -f "$COMPOSE_FILE" exec -T -e STOP_FILE="$STOP_FILE" backend sh -lc '
  rm -f "$STOP_FILE"
  test ! -f "$STOP_FILE"
'

echo "[ok] stop 요청 파일 제거: $STOP_FILE"
