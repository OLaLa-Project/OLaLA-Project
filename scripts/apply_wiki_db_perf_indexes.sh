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

POSTGRES_DB="${POSTGRES_DB:-olala}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
COMPOSE_FILE="infra/docker/docker-compose.beta.yml"

echo "[1/5] wiki-db 기동"
docker compose -f "$COMPOSE_FILE" up -d wiki-db

echo "[2/5] 확장 설치(pgvector + pg_trgm)"
docker compose -f "$COMPOSE_FILE" exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
SQL

echo "[3/5] 기본 성능 인덱스 적용"
docker compose -f "$COMPOSE_FILE" exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_wiki_pages_title_trgm
  ON public.wiki_pages USING gin (title gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_wiki_chunks_content_fts_simple
  ON public.wiki_chunks USING gin (to_tsvector('simple', content));

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_wiki_chunks_page_chunk_idx
  ON public.wiki_chunks (page_id, chunk_idx);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_wiki_chunks_missing_embedding
  ON public.wiki_chunks (page_id, chunk_id)
  WHERE embedding IS NULL;
SQL

echo "[4/5] 통계 갱신"
docker compose -f "$COMPOSE_FILE" exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
ANALYZE public.wiki_pages;
ANALYZE public.wiki_chunks;
SQL

echo "[5/5] 결과 확인"
docker compose -f "$COMPOSE_FILE" exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT extname FROM pg_extension WHERE extname IN ('vector','pg_trgm') ORDER BY extname;"
docker compose -f "$COMPOSE_FILE" exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT indexname FROM pg_indexes WHERE schemaname='public' AND tablename IN ('wiki_pages','wiki_chunks') ORDER BY indexname;"

echo "[ok] wiki DB 성능 인덱스 적용 완료"
