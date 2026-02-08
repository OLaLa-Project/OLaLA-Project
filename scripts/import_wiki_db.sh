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

echo "[1/5] DB 컨테이너 기동"
docker compose -f infra/docker/docker-compose.beta.yml up -d wiki-db

echo "[2/6] pgvector/스키마 준비"
docker compose -f infra/docker/docker-compose.beta.yml exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS public.wiki_pages (
  page_id BIGINT PRIMARY KEY,
  title TEXT NOT NULL,
  url TEXT NULL
);
CREATE TABLE IF NOT EXISTS public.wiki_chunks (
  chunk_id BIGINT PRIMARY KEY,
  page_id BIGINT NOT NULL REFERENCES public.wiki_pages(page_id) ON DELETE CASCADE,
  chunk_idx INTEGER NOT NULL,
  content TEXT NOT NULL,
  embedding vector(768) NULL
);
CREATE INDEX IF NOT EXISTS ix_wiki_pages_title ON public.wiki_pages (title);
CREATE INDEX IF NOT EXISTS ix_wiki_chunks_page_id ON public.wiki_chunks (page_id);
CREATE INDEX IF NOT EXISTS ix_wiki_chunks_chunk_idx ON public.wiki_chunks (chunk_idx);
SQL

echo "[3/6] 기존 데이터 정리"
docker compose -f infra/docker/docker-compose.beta.yml exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
TRUNCATE TABLE public.wiki_chunks RESTART IDENTITY CASCADE;
TRUNCATE TABLE public.wiki_pages RESTART IDENTITY CASCADE;
SQL

echo "[4/6] CSV 적재 (대용량)"
docker compose -f infra/docker/docker-compose.beta.yml exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
SET statement_timeout = 0;
COPY public.wiki_pages(page_id, title)
FROM '/import/wiki_pages.csv'
WITH (FORMAT csv, HEADER true, QUOTE '"', ESCAPE '"');

COPY public.wiki_chunks(chunk_id, page_id, chunk_idx, content)
FROM '/import/wiki_chunks.csv'
WITH (FORMAT csv, HEADER true, QUOTE '"', ESCAPE '"');
SQL

echo "[5/6] 성능 인덱스/통계 갱신"
docker compose -f infra/docker/docker-compose.beta.yml exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS ix_wiki_pages_title_trgm
  ON public.wiki_pages USING gin (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_wiki_chunks_content_fts_simple
  ON public.wiki_chunks USING gin (to_tsvector('simple', content));

CREATE INDEX IF NOT EXISTS ix_wiki_chunks_page_chunk_idx
  ON public.wiki_chunks (page_id, chunk_idx);

CREATE INDEX IF NOT EXISTS ix_wiki_chunks_missing_embedding
  ON public.wiki_chunks (page_id, chunk_id)
  WHERE embedding IS NULL;

ANALYZE public.wiki_pages;
ANALYZE public.wiki_chunks;
SQL

echo "[6/6] 검증"
docker compose -f infra/docker/docker-compose.beta.yml exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT COUNT(*) AS wiki_pages FROM public.wiki_pages;"
docker compose -f infra/docker/docker-compose.beta.yml exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT COUNT(*) AS wiki_chunks FROM public.wiki_chunks;"

echo "[ok] wiki DB import 완료"
