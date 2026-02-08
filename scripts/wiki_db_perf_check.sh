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
QUERY_TEXT="${1:-코로나}"
OUT_DIR="docs/perf"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_FILE="$OUT_DIR/wiki-db-perf-$STAMP.txt"

mkdir -p "$OUT_DIR"

echo "[info] query=$QUERY_TEXT"
echo "[info] output=$OUT_FILE"

{
  echo "# Wiki DB Performance Report"
  echo "generated_at=$(date -Iseconds)"
  echo "query=$QUERY_TEXT"
  echo
  echo "## table stats"
  docker compose -f "$COMPOSE_FILE" exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "SELECT relname, n_live_tup::bigint AS rows, pg_size_pretty(pg_total_relation_size(relid)) AS total_size FROM pg_stat_user_tables WHERE relname IN ('wiki_pages','wiki_chunks') ORDER BY relname;"
  echo
  echo "## embedding coverage"
  docker compose -f "$COMPOSE_FILE" exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "SELECT COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS emb_nonnull, COUNT(*) AS total FROM public.wiki_chunks;"
  echo
  echo "## explain title_ilike"
  docker compose -f "$COMPOSE_FILE" exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "EXPLAIN (ANALYZE, BUFFERS) SELECT page_id, title FROM public.wiki_pages WHERE title ILIKE '%' || '$QUERY_TEXT' || '%' ORDER BY page_id LIMIT 20;"
  echo
  echo "## explain chunk_fts_candidate_cte"
  docker compose -f "$COMPOSE_FILE" exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "EXPLAIN (ANALYZE, BUFFERS) WITH q AS (SELECT plainto_tsquery('simple', '$QUERY_TEXT') AS tsq), matched AS (SELECT c.page_id, ts_rank_cd(to_tsvector('simple', c.content), q.tsq) AS r FROM public.wiki_chunks c CROSS JOIN q WHERE to_tsvector('simple', c.content) @@ q.tsq ORDER BY r DESC LIMIT 200) SELECT DISTINCT m.page_id, p.title FROM matched m JOIN public.wiki_pages p ON p.page_id = m.page_id LIMIT 20;"
  echo
  echo "## explain fetch_window"
  docker compose -f "$COMPOSE_FILE" exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "EXPLAIN (ANALYZE, BUFFERS) SELECT content FROM public.wiki_chunks WHERE page_id = 12 AND chunk_idx >= 0 AND chunk_idx <= 5 ORDER BY chunk_idx ASC;"
  echo
  echo "## explain vector_search_topk (if embeddings exist)"
  docker compose -f "$COMPOSE_FILE" exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<SQL
DO \$\$
DECLARE emb_count bigint;
BEGIN
  SELECT COUNT(*) INTO emb_count FROM public.wiki_chunks WHERE embedding IS NOT NULL;
  IF emb_count = 0 THEN
    RAISE NOTICE 'SKIP vector explain: no embeddings';
  ELSE
    RAISE NOTICE 'RUN vector explain: embeddings=%', emb_count;
  END IF;
END
\$\$;
SQL
  docker compose -f "$COMPOSE_FILE" exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "SELECT CASE WHEN COUNT(*) = 0 THEN 'SKIPPED' ELSE 'READY' END AS vector_check FROM public.wiki_chunks WHERE embedding IS NOT NULL;"
  echo
  echo "## index list"
  docker compose -f "$COMPOSE_FILE" exec -T wiki-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public' AND tablename IN ('wiki_pages','wiki_chunks') ORDER BY tablename, indexname;"
} >"$OUT_FILE"

echo "[ok] report generated: $OUT_FILE"
