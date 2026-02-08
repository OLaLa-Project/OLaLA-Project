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
STOP_FILE="${1:-${EMBED_STOP_FILE:-/tmp/wiki-embed.stop}}"

docker compose -f "$COMPOSE_FILE" up -d wiki-db backend >/dev/null

ROW_RAW="$(docker compose -f "$COMPOSE_FILE" exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F '|' -c "SELECT COUNT(*)::bigint, COUNT(*) FILTER (WHERE embedding IS NULL)::bigint FROM public.wiki_chunks;")"
TOTAL="${ROW_RAW%%|*}"
MISSING="${ROW_RAW##*|}"
EMBEDDED=$((TOTAL - MISSING))

if [ "$TOTAL" -gt 0 ]; then
  PCT="$(awk -v e="$EMBEDDED" -v t="$TOTAL" 'BEGIN { printf "%.2f", (e*100.0)/t }')"
else
  PCT="0.00"
fi

if docker compose -f "$COMPOSE_FILE" exec -T -e STOP_FILE="$STOP_FILE" backend sh -lc '[ -f "$STOP_FILE" ]'; then
  STOP_STATUS="present"
else
  STOP_STATUS="absent"
fi

echo "wiki_embeddings_ready=${WIKI_EMBEDDINGS_READY:-false}"
echo "embedded=$EMBEDDED"
echo "missing=$MISSING"
echo "total=$TOTAL"
echo "coverage_pct=$PCT"
echo "stop_file=$STOP_FILE"
echo "stop_file_status=$STOP_STATUS"
