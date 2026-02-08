# STEP-07 Wiki DB Index and Performance Baseline

- Date: 2026-02-07
- Status: Completed
- Scope: Phase 2의 `인덱스/성능 기준 정리` 완료

## 목표
wiki DB(`wiki_pages`, `wiki_chunks`)의 검색 병목을 줄이고, 재현 가능한 성능 기준/측정 절차를 문서와 스크립트로 고정한다.

## 수행 작업
1. 실제 쿼리 패턴 분석
- 기준 파일:
  - `services/backend/app/orchestrator/database/repos/wiki_repo.py`
- 확인된 핵심 경로:
  - `title ILIKE` 기반 페이지 후보 검색
  - `chunk FTS` 기반 후보 검색(CTE + rank)
  - `fetch_window(page_id, chunk_idx)`

2. 인덱스 적용 전 상태 점검
- 기존 인덱스는 `title/page_id/chunk_idx` 기본 BTREE 위주
- `pg_trgm` 부재, FTS GIN 인덱스 부재 확인
- 사전 측정(기준 쿼리):
  - title ILIKE 약 `997 ms`
  - 단순 FTS JOIN 쿼리 약 `4.1 s`

3. 성능 인덱스 적용 스크립트 추가
- 파일: `scripts/apply_wiki_db_perf_indexes.sh`
- 적용 항목:
  - 확장: `pg_trgm`, `vector`
  - 인덱스:
    - `ix_wiki_pages_title_trgm`
    - `ix_wiki_chunks_content_fts_simple`
    - `ix_wiki_chunks_page_chunk_idx`
    - `ix_wiki_chunks_missing_embedding`
  - `ANALYZE` 수행

4. 성능 점검 스크립트 추가
- 파일: `scripts/wiki_db_perf_check.sh`
- 리포트 생성:
  - `docs/perf/wiki-db-perf-<timestamp>.txt`
- 측정 항목:
  - `title_ilike`
  - `chunk_fts_candidate_cte` (실제 코드 경로 형태)
  - `fetch_window`
  - vector 경로 가능 여부

5. import 파이프라인 보강
- 파일: `scripts/import_wiki_db.sh`
- 변경:
  - CSV 적재 후 성능 인덱스/통계 갱신 단계를 기본 포함

6. 기준 문서화
- 파일: `docs/WIKI_DB_PERFORMANCE_BASELINE.md`
- 포함:
  - 필수 인덱스 기준
  - 성능 목표치
  - 측정/검증 명령
  - 주의사항(비권장 쿼리 형태)

## 검증 결과
리포트: `docs/perf/wiki-db-perf-20260207-042215.txt`

- `title_ilike`: `1.323 ms`
- `chunk_fts_candidate_cte`: `56.975 ms`
- `fetch_window`: `0.044 ms`
- `vector_search_topk`: `SKIPPED` (embedding 없음)

핵심 확인:
- title 검색이 trigram GIN을 사용함(`Bitmap Index Scan on ix_wiki_pages_title_trgm`)
- chunk FTS가 GIN을 사용함(`Bitmap Index Scan on ix_wiki_chunks_content_fts_simple`)

## 기존 대비 변경 사항
- 기존:
  - 성능 인덱스 기준/적용 절차가 명시되지 않음
  - import 후 FTS/trigram 인덱스가 자동 보장되지 않음
- 변경:
  - 인덱스 적용/점검/문서화가 스크립트 기반으로 표준화
  - import 시점에 성능 인덱스 + 통계 갱신 내장
- 효과:
  - 재배포/재적재 후에도 일관된 성능 상태 재현 가능

## 남은 리스크
1. vector 검색 성능 기준 미확정
- embedding 데이터가 0건이라 vector 인덱스/latency 기준은 다음 단계(임베딩 배치) 이후 확정 가능

2. 단순 JOIN 기반 FTS 쿼리 오용 가능성
- 코드 밖에서 비권장 쿼리 형태를 사용하면 느린 실행계획이 나올 수 있음

## 다음 단계
- STEP-08: `임베딩 배치 정책 수립` (생성 전략, 배치 크기, 재시도/중단 복구, 운영 기준)
