# Wiki DB Index and Performance Baseline

## 목적
`wiki_pages` / `wiki_chunks` 기반 검색 경로에서 안정적인 응답속도를 유지하기 위한 인덱스 기준과 측정 기준을 고정한다.

## 적용 인덱스 기준
아래 인덱스는 기본 운영 기준이다.

- `ix_wiki_pages_title_trgm` (GIN, `title gin_trgm_ops`)
- `ix_wiki_chunks_content_fts_simple` (GIN, `to_tsvector('simple', content)`)
- `ix_wiki_chunks_page_chunk_idx` (BTREE, `(page_id, chunk_idx)`)
- `ix_wiki_chunks_missing_embedding` (BTREE, `(page_id, chunk_id) WHERE embedding IS NULL`)

확장 기준:
- `vector` (필수)
- `pg_trgm` (필수)

## 운영 스크립트
프로덕션 루트에서 실행:

```bash
bash scripts/apply_wiki_db_perf_indexes.sh
bash scripts/wiki_db_perf_check.sh 코로나
```

리포트 경로:
- `docs/perf/wiki-db-perf-<timestamp>.txt`

## 성능 기준 (베타)
단일 노드/로컬 Docker 기준의 운영 가이드라인:

1. `title ILIKE` (`wiki_pages`)  
- 목표: `EXPLAIN ANALYZE Execution Time < 20ms`

2. `chunk FTS candidate CTE` (`wiki_chunks -> wiki_pages`)  
- 목표: `EXPLAIN ANALYZE Execution Time < 150ms`

3. `fetch_window` (`page_id + chunk_idx`)  
- 목표: `EXPLAIN ANALYZE Execution Time < 5ms`

4. `vector_search_topk`  
- 현재: embedding 미생성 상태면 `SKIPPED` 허용
- 전환 기준: `embedding IS NOT NULL` 비율이 유의미해지면(권장 30%+) 벡터 인덱스(HNSW/IVFFLAT) 별도 적용

## 현재 측정값 (2026-02-07)
리포트: `docs/perf/wiki-db-perf-20260207-042215.txt`

- `title_ilike`: `1.323 ms`
- `chunk_fts_candidate_cte`: `56.975 ms`
- `fetch_window`: `0.044 ms`
- `vector_search_topk`: `SKIPPED` (no embeddings)

## 주의사항
- `SELECT DISTINCT ... JOIN ... WHERE to_tsvector(...)` 형태의 단순 쿼리는 플래너가 비효율 경로를 선택할 수 있다.
- 실제 코드 경로처럼 `matched CTE + LIMIT` 형태를 유지해야 FTS 인덱스 효과가 안정적으로 나온다.
- GIN 인덱스 생성 중 `word is too long to be indexed` NOTICE는 정상이며, 2047자 초과 토큰 무시 동작이다.
