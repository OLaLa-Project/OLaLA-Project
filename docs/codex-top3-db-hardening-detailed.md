# Codex 작업 지시서(v1): DB 검색/저장 Top 3 Hardening (안정성/보안/예측가능성)

- 작성일: 2026-02-06
- 상태: APPLIED v1 (2026-02-06)
- 대상: `backend/app/*` (Stage03 collect, wiki repo/usecase, API, analysis 저장)
- Top3 목표:
  1) 온라인 경로에서 임베딩 채우기(write) 금지 → read-only 보장  
  2) Wiki FTS 후보검색 SQL 안전화 → f-string로 사용자 입력을 SQL에 삽입하는 패턴 제거  
  3) 트랜잭션/commit 경계 통일 → repo 내부 commit 제거, 상위 경계에서 커밋  

---

## 0) 배경/현상 요약

### 현재 리스크 3가지
- 온라인 요청 처리 중 `embed_missing=True`가 켜지면 DB write + Ollama 호출이 섞여 지연/락/비용이 급증할 수 있음.
- `WikiRepository.find_candidates_by_chunk_fts()`가 사용자 입력을 f-string으로 SQL에 직접 삽입하는 코드가 있어 쿼리 파손/Injection 표면이 존재.
- repo 메서드 내부 `commit()`은 상위 레이어(서비스/API)가 트랜잭션 경계를 잡기 어렵게 만들어 부분 커밋/예측불가능성을 유발.

### Non-Goals (이번 범위 밖)
- 한국어 형태소 분석기 도입(mecab 등)
- wiki/rag 테이블 통합/삭제
- 랭킹/스코어 가중치 대개편

---

## 1) 변경 1: Online 임베딩 금지(`embed_missing`)로 read-only 보장

### 1.1 정책(결정)
- 기본값: `embed_missing=False`
- 파이프라인 Stage03 collect에서 Wiki 검색 호출은 **항상 `embed_missing=False`로 강제** (온라인 파이프라인은 read-only)
- 예외(관리/디버그): 특정 API에서만 env 가드로 허용
  - env `ALLOW_ONLINE_EMBED_MISSING=true`일 때만 request의 `embed_missing=true`를 반영
  - 기본은 거부(override false) + warning 로그 1줄

**주의**
- `/truth/check` 요청 스키마에는 `embed_missing`가 없다. (API 오버라이드는 embed_missing를 “받는 엔드포인트”에만 적용)
- 온라인 파이프라인의 write 차단은 Stage03 collect 강제 false가 핵심.

### 1.2 변경 대상(정확한 파일)
- 기본값 변경
  - `backend/app/core/wiki_schemas.py`
    - `WikiSearchRequest.embed_missing: True -> False`
  - `backend/app/api/dashboard.py`
    - `TeamARetrieveRequest.embed_missing: True -> False`
- Stage03 collect 강제 오버라이드
  - `backend/app/stages/stage03_collect/node.py`
    - `_search_wiki()`에서 `retrieve_wiki_hits(..., embed_missing=False, ...)`로 고정
- env 가드(선택, 하지만 권장)
  - `backend/app/api/wiki.py` (`/api/wiki/search`)
  - `backend/app/api/rag.py` (`/api/rag/wiki/search`)
  - `backend/app/api/dashboard.py` (`/api/team-a/retrieve`)
  - 처리 규칙:
    - `ALLOW_ONLINE_EMBED_MISSING`가 true가 아니면 `req.embed_missing`를 무조건 false로 덮기
    - 덮었으면 `logger.warning("embed_missing overridden to false")` 1줄 (가능하면 trace_id 포함)

### 1.3 성공 기준
- Stage03 collect를 포함한 `/api/truth/check` 실행 중 `wiki_chunks.embedding`이 변하지 않는다.
- 온라인 요청이 Ollama embedding 호출/DB write를 유발하지 않는다.
- 임베딩은 배치 워커(예: `.wiki/embed_chunks.py`, `backend/embed_chunks.py`)로만 진행한다.

### 1.4 검증 SQL
```sql
SELECT COUNT(*) FROM public.wiki_chunks WHERE embedding IS NULL;
SELECT COUNT(*) FROM public.rag_chunks  WHERE embedding IS NULL;
```

---

## 2) 변경 2: Wiki FTS 후보검색 SQL 안전화 (f-string 입력 삽입 금지)

### 2.1 문제(원인)
`find_candidates_by_chunk_fts()`가 현재 키워드를 SQL 문자열에 직접 삽입하는 형태여서:
- `'`/특수문자 포함 시 쿼리 파손
- Injection 표면
- 유튜브 전사 등 긴 입력에서 파싱/성능 리스크

### 2.2 정책(결정)
FTS 후보검색은 아래로 통일:
- `websearch_to_tsquery('simple', :q)` + 파라미터 바인딩
- 입력 정규화 + 길이 제한 적용
  - 예: 180자 cap
  - 제어문자 제거, 공백 정리
  - `&`는 공백으로 치환(AND 의도 유지)
- **FTS 파싱/실행 실패 시:** 예외를 삼키고 **빈 결과 반환(500 금지)**
  - 상위 `wiki_usecase.retrieve_wiki_hits()`는 title 후보/벡터 후보로 계속 진행 가능

### 2.3 변경 대상(정확한 파일)
- `backend/app/gateway/database/repos/wiki_repo.py`
  - `find_candidates_by_chunk_fts()` 재작성
  - `_normalize_fts_query(q: str, max_len: int = 180) -> str` 추가
  - “동적 SQL 조립” 제거: 모든 값은 params로 전달

### 2.4 권장 SQL 형태(예시)
```sql
WITH q AS (
  SELECT websearch_to_tsquery('simple', :q) AS tsq
),
matched AS (
  SELECT
    c.page_id,
    ts_rank_cd(to_tsvector('simple', c.content), q.tsq) AS r
  FROM public.wiki_chunks c
  CROSS JOIN q
  WHERE to_tsvector('simple', c.content) @@ q.tsq
),
best AS (
  SELECT page_id, MAX(r) AS score
  FROM matched
  GROUP BY page_id
)
SELECT p.page_id, p.title
FROM best b
JOIN public.wiki_pages p ON p.page_id = b.page_id
ORDER BY b.score DESC, p.page_id ASC
LIMIT :limit;
```

### 2.5 필수 테스트 케이스
- `q="삼성전자"`
- `q="삼성전자 & 2024"`
- `q="a' OR 1=1; --"` (에러 없이 실행, 결과는 정상 범위)
- `q` 1000자 이상(길이 cap 적용 후 예외 없이 실행)

---

## 3) 변경 3: commit 경계 통일 (repo commit 제거, Top3는 “B안”)

### 3.1 현재 구조 문제
repo 내부 `commit()`은 상위 레이어에서 원자성/롤백 경계를 만들기 어렵다.

### 3.2 정책(결정) — 이번 Top3는 B안으로 고정
- **B안(이번 작업의 표준):** repo는 `commit/rollback` 금지, **API/usecase에서 명시적으로 commit**
- `transaction()`을 “전면 표준화(A안)” 하는 건 변경 폭이 커서 **별도 리팩토링 이슈로 분리**

### 3.3 변경 대상(정확한 파일)
- repo에서 `commit()` 제거
  - `backend/app/gateway/database/repos/wiki_repo.py: update_chunk_embeddings()`
  - `backend/app/gateway/database/repos/rag_repo.py: update_chunk_embeddings()`
  - `backend/app/gateway/database/repos/analysis_repo.py: save_analysis()`
- commit을 호출자에서 수행
  - `backend/app/api/truth_check.py`
    - `AnalysisRepository(db).save_analysis(...)` 이후 `db.commit()`
    - 실패 시 FastAPI 요청 단위로 예외 처리(rollback 필요하면 `db.rollback()`)

**참고**
- Online `embed_missing`를 막으면 `update_chunk_embeddings()`는 주로 배치/관리 경로에서만 호출될 가능성이 높다.
- 그래도 “repo는 commit 금지” 원칙은 유지(예측가능성).

### 3.4 성공 기준
- `/truth/check` 실행 시 `analysis_results`가 정상 저장된다.
- 예외 발생 시 “반쯤 저장” 같은 부분 커밋이 없다.

---

## 4) PR 분해 + 작업 순서(권장)

### PR1: Online embed 금지(read-only)
- default false
- Stage03 collect 강제 false
- (선택) API env 가드 + override warning

### PR2: Wiki FTS 안전화
- `find_candidates_by_chunk_fts()` parameterize + normalize + cap
- 에러 시 빈 결과 반환

### PR3: commit 경계 통일(B안)
- repo commit 제거
- `/truth/check` 등 write endpoint에서 commit 수행

---

## 5) 최종 체크리스트
- [ ] 온라인 Stage03 collect에서 `embed_missing=True` 코드 경로가 0개
- [ ] `wiki_repo.find_candidates_by_chunk_fts()`에 사용자 입력이 SQL 문자열로 들어가는 코드 0개
- [ ] repo에 `commit()` 호출 0개
- [ ] `/truth/check`가 `analysis_results` 저장 성공
