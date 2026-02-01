# Gemini 작업 지시서: Gateway 리팩토링 후 RAG(위키 검색) 회귀 복구 + FTS/Vector/Lexical 개선

## 0) 목표 (정확히 이 3개만 달성)
1. **회귀 복구**: 리팩토링 전 “잘 되던” 위키 RAG 검색 품질/동작을 그대로 되살린다.  
2. **FTS 개선**: 후보 페이지(Candidates)를 **title FTS**가 아니라 **chunk(content) FTS 기반**으로 뽑도록 개선한다.  
3. **Hybrid rerank**: Vector 결과(oversample)에 대해 **FTS rank를 추가로 계산해 재정렬**하여 품질을 끌어올린다.

---

## 1) 현 상태에서 “회귀”가 터지는 전형적 원인
Gateway 리팩토링 과정에서 DB 접근 레이어가 **2개(구 레이어 vs 신 레이어)**로 갈라지면서, 아래 문제가 쉽게 발생한다.

### 1-1. 같은 기능을 서로 다른 모듈에서 “중복 구현” → 로직 드리프트
- `services/wiki_retriever.py`는 기존 로직(후보 페이지 → hit 생성 → window 확장/필터 → rerank)을 갖고 있고,  
- `gateway/*` 하위에 새로 만든 repo/usecase가 따로 존재하면, API 경로에 따라 서로 다른 로직이 실행되며 품질이 흔들린다.

### 1-2. pg_trgm / similarity 타입 이슈 (SQLAlchemy bindparam이 `unknown`으로 들어오는 케이스)
- `similarity(title, :q)`가 `similarity(varchar, unknown)` 같은 형태로 해석돼 에러가 날 수 있다.  
- 해결: `:q::text`로 명시 캐스팅, 또는 bindparam에 type 지정.

### 1-3. FTS 인덱스가 있는데도 Seq Scan으로 빠지는 케이스
- expression GIN index가 있어도 통계/플래너 비용 설정이 엇나가면 `Seq Scan`이 뜰 수 있다.
- 해결: (A) `ANALYZE`/`VACUUM (ANALYZE)`로 통계 갱신, (B) 필요하면 `content_tsv` STORED 컬럼 + GIN으로 “확정”한다.

---

## 2) 작업 범위/원칙
### 2-1. “기존 방식”의 기준
- 기존 방식 = **services/wiki_retriever.py 중심의 파이프라인**을 기준으로 삼는다.
- Gateway는 **세션 관리 + repo DI(주입)** 수준으로만 얇게 유지한다.
- 즉, “검색 알고리즘”은 wiki_retriever 쪽을 단일 소스로 두고, gateway는 그 아래를 받쳐주는 구조로 정리한다.

### 2-2. 수정 파일 (최소 변경 기준)
- `app/services/wiki_retriever.py`  ✅ (후보 페이지/Hybrid rerank 핵심)
- `app/db/repo.py` 또는 `app/gateway/database/repos/wiki_repo.py` 중 **한쪽만** ✅ (SQL 묶어서 관리)
- (선택) `app/db/repos/wiki_repo.py` ✅ (window fetch 등 보조)
- `app/api/wiki.py` ✅ (실제로 어떤 경로가 호출되는지 단일화)

> **중요:** DB access 레이어를 2개 유지하면 회귀는 계속 난다.  
> “구 레이어를 유지할지 / 신 레이어로 옮길지” 둘 중 하나로 **단일화**해야 한다.

---

## 3) 빠른 진단 체크리스트 (먼저 이거부터)
### 3-1. 지금 API가 실제로 어떤 검색 로직을 타는지 확인
1) `api/wiki.py`에서 호출하는 usecase/서비스 함수가 무엇인지 확인  
2) 요청 한 번 넣고 서버 로그에 “mode / candidates / hits / debug”가 찍히는지 확인  
3) `services/wiki_retriever.retrieve_wiki_hits()`가 호출되는지 확인 (기준점)

### 3-2. DB 확장 확인 (olala DB 기준)
```sql
SELECT extname FROM pg_extension WHERE extname IN ('vector','pg_trgm');
```
없으면:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### 3-3. 인덱스 확인 (olala DB 기준)
```sql
-- wiki_chunks content FTS (GIN expression index)
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname='public' AND tablename='wiki_chunks';

-- wiki_pages title trigram (GIN)
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname='public' AND tablename='wiki_pages';
```

---

## 4) 개선 1: 후보 페이지를 “chunk FTS 기반”으로 변경 (2순위 항목)
현재 후보 페이지는 title 중심/union 중심일 가능성이 높다.  
이를 “content(chunk)에서 먼저 매칭 → page_id로 그룹핑”으로 바꾼다.

### 4-1. 추천 SQL (대량 데이터 안정형: chunk match를 먼저 top-N으로 제한)
```sql
WITH q AS (
  SELECT plainto_tsquery('simple', :q) AS tsq
),
matched AS (
  SELECT
    c.page_id,
    ts_rank_cd(to_tsvector('simple', c.content), q.tsq) AS r
  FROM public.wiki_chunks c
  CROSS JOIN q
  WHERE to_tsvector('simple', c.content) @@ q.tsq
  ORDER BY r DESC
  LIMIT :chunk_oversample
)
SELECT
  m.page_id,
  p.title,
  MAX(m.r) AS rank,
  COUNT(*) AS hit_chunks
FROM matched m
JOIN public.wiki_pages p ON p.page_id = m.page_id
GROUP BY m.page_id, p.title
ORDER BY rank DESC, hit_chunks DESC
LIMIT :page_limit;
```

- `chunk_oversample`는 보통 `page_limit * 50 ~ 200` 추천.
- 이 방식이면 `wiki_chunks_content_fts`(GIN) 인덱스를 안정적으로 탄다.

### 4-2. 구현 위치
- `services/wiki_retriever.py`에 `_candidate_pages_fts()`를 교체하거나
- 새 함수 `_candidate_pages_chunk_fts()` 추가 후 `candidates_union`에 포함.

---

## 5) 개선 2: Hybrid rerank (FTS가 강하면 이게 “최종 치트키”)
요지:
- Vector 검색은 recall이 좋음 (oversample로 넉넉히 뽑기)
- FTS rank는 precision이 좋음 (이걸 rerank signal로 섞기)

### 5-1. 추천 전략 (가장 구현 쉬운 버전)
1) Vector로 `oversample_k = top_k * RERANK_OVERSAMPLE` 만큼 `chunk_id`들을 가져온다.
2) 가져온 `chunk_id` 집합에 대해 **FTS rank를 “후계산”**한다.
3) 최종 점수:
   - `vec_score = 1 / (1 + dist)` (cosine distance 기반)
   - `fts_score = ts_rank_cd(...)` (0~대략 1.x)
   - `final = w_vec*vec_score + w_fts*fts_score + w_title*title_score + w_lex*lex_score`
4) `final DESC`로 정렬 후 top_k로 자른다.

### 5-2. FTS rank 후계산 SQL (chunk_id 제한)
```sql
WITH q AS (
  SELECT plainto_tsquery('simple', :q) AS tsq
)
SELECT
  c.chunk_id,
  ts_rank_cd(to_tsvector('simple', c.content), q.tsq) AS fts_rank
FROM public.wiki_chunks c
CROSS JOIN q
WHERE c.chunk_id = ANY(:chunk_ids)
;
```

### 5-3. 구현 포인트
- `services/wiki_retriever._rerank_vector_hits()` 내부에 `fts_rank_map`을 추가해서 final_score에 반영.
- `:chunk_ids`는 `ARRAY(BigInteger)`로 bindparam 타입을 명시.

---

## 6) Lexical 구조 점검/개선 포인트 (지금 구조 유지 + 작은 수술)
### 6-1. 제목/트라이그램 후보에서 타입 캐스팅 고정
SQLAlchemy 바인딩 이슈 방지:
```sql
similarity(title, (:q)::text)
```
또는 bindparam에 `type_=Text()` 지정.

### 6-2. “키워드 하드룰” 필터 유지
기존 방식이 window 확장 후 **모든 키워드 포함 여부**로 필터링한다면, 이건 precision에 매우 도움 된다.  
(다만 recall이 떨어질 수 있으니 `window`/`keywords_used` 설계를 조절)

---

## 7) 성능: FTS가 Seq Scan 잡히는 문제를 “확실히” 없애는 옵션
> 데이터가 5M chunk 급이면, 플래너/통계 꼬임으로 가끔 Seq Scan이 뜬다.

### 옵션 A (가벼움): 통계 갱신
```sql
VACUUM (ANALYZE) public.wiki_chunks;
VACUUM (ANALYZE) public.wiki_pages;
```

### 옵션 B (무거움, 확실): STORED tsvector 컬럼
```sql
ALTER TABLE public.wiki_chunks
  ADD COLUMN content_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED;

CREATE INDEX CONCURRENTLY wiki_chunks_content_tsv_gin
  ON public.wiki_chunks USING gin (content_tsv);
```
이후 쿼리는:
```sql
WHERE content_tsv @@ plainto_tsquery('simple', :q)
```

---

## 8) “Gateway 리팩토링” 정리 방향 (회귀 안 나게 하는 최소 구조)
### 권장 아키텍처
- `api/wiki.py` → `services/wiki_usecase.py` → `services/wiki_retriever.py`
- DB 세션은 gateway가 만들되, 검색 로직은 retriever에만 둔다.
- repo는 “SQL 묶음”만 제공 (find_pages_*, vector_search, fts_rank_for_chunk_ids 등)

### 금지
- gateway 쪽에 “retriever 로직 복제본”을 만들지 말 것 (로직 드리프트로 회귀 반복)

---

## 9) 수용 기준(완료 정의)
### 기능
- `/api/wiki/search`에서 `search_mode=fts|vector|lexical|auto` 모두 동작
- `embed_missing=true`에서 embedding 채우기 동작 (무한 루프/폭주 없음)

### 품질
- 대표 쿼리(예: “윤석열 탄핵 절차”, “전기차 보조금”, “딥러닝 옵티마이저” 등)로:
  - `fts`가 최소 1개 이상의 hit을 내고
  - `hybrid rerank`에서 상위 결과가 체감으로 개선됨(최소 5~10개 샘플 확인)

### 성능
- chunk FTS 후보 생성 쿼리에서 GIN index 기반 `Bitmap Index Scan`이 뜨는지 확인
- top_k=8, page_limit=8 기준 응답시간이 “지연 없는 수준”으로 유지

---

## 10) 작업 순서 (Gemini에게 그대로 시키면 됨)
1) `api/wiki.py`가 호출하는 경로를 단일화해서 “기존 retriever”만 타게 만든다.
2) `similarity()` 타입 캐스팅 문제를 제거한다. (에러 재발 방지)
3) 후보 페이지를 chunk FTS 기반으로 교체한다.
4) vector oversample + FTS rank 후계산 rerank를 넣는다.
5) (필요 시) VACUUM/ANALYZE 또는 content_tsv 옵션을 적용한다.
6) curl 샘플/EXPLAIN으로 수용 기준 체크 후 PR 마무리.

---
