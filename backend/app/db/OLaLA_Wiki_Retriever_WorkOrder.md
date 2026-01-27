# OLaLA-Project: Wiki Retriever를 “하이브리드(lexical → (옵션) vector rerank → window pack)”로 고치기 (Codex 작업지시서)

## 배경 / 현재 상태(문제 정의)
- DB에는 `wiki_pages`(734,082) / `wiki_chunks`(5,324,201)가 있음.
- `wiki_chunks.embedding IS NOT NULL` 청크가 **매우 적음(약 1,161개 수준)** → vector-only 검색은 거의 랜덤에 가까운 결과가 튀는 게 정상.
- 실제로 `/api/wiki/search` 및 `/api/rag/wiki/search`가 “vector 기반” 전제일 때 **엉뚱한 문서(예: 가위)**가 상위로 뜨는 현상 확인됨.
- 목표는 “Wiki는 최신 사건 검증이 아니라 **배경/정의/제도/기관/과거 유사 사례** 용도”로 안정적으로 쓰는 것.
- 결론: Wiki 검색은 **절대 vector-only 금지**. “lexical 후보 생성”이 기본이 되어야 함.

---

## 목표(완료 조건)
### 반드시 만족해야 함
1. `/api/wiki/search` 요청에서 **embedding이 0개인 페이지여도** 관련 페이지(예: `대한민국 대통령` page_id=2342)를 candidate/hit로 반환해야 함.
2. `embed_missing=true`일 때 “매 쿼리마다 대량 임베딩”이 아니라,
   - **이번 요청에서 뽑힌 후보 page에 한정**해서
   - **캡(cap) 걸고**(예: 최대 200~500 chunks) 임베딩을 채우는 “캐시”로 동작해야 함.
3. `/api/wiki/search`와 `/api/rag/wiki/search`가 **동일한 core retriever**를 사용하도록 통합(중복 로직 제거).
4. 결과가 없을 때도 “조용히 빈 배열”만 반환하지 말고,
   - candidates가 비었는지
   - lexical 단계가 실패했는지
   - embed가 없는 상태라 vector rerank를 못했는지
   를 응답/로그로 최소한 구분 가능해야 함.

---

## Non-goals(이번 작업에서 안 함)
- “현재 대통령이 누구냐” 같은 **최신성 요구 질문에 대해 정답을 확정**하는 기능(그건 News RAG/공식소스가 담당).
- Wiki 전체(532만 chunks)를 일괄 임베딩 하는 배치 작업(별도 파이프라인으로 분리).
- 위키 덤프 업데이트/재수집.

---

## 현재 코드 위치(수정 대상)
- 라우팅:
  - `/app/app/api/wiki.py` : `/api/wiki/search` → `vector_search_with_window(...)`
  - `/app/app/api/rag.py`  : `/api/rag/wiki/search` → `retrieve_wiki_context(...)`
- 레포/서비스(현행 확인 필요):
  - `/app/app/db/repos/wiki_repo.py` : `vector_search_with_window` 존재
  - `/app/app/services/wiki_rag.py`  : `retrieve_wiki_context` 존재
  - `/app/app/services/wiki_embedder.py` : `ensure_wiki_embeddings`, `extract_keywords` 등 존재(이미 사용 중)

> **주의:** 예전 import인 `app.db.repo`는 없음. 현재는 `app.db.repos.*` 경로 사용.

---

## 최종 설계(핵심)
### Wiki Retriever = 3단계 파이프라인
1) **Lexical 후보 페이지 생성(필수)**
- 입력: `question`
- 출력: `candidate_pages: list[{page_id,title,score}]`
- 방법(우선순위):
  - (A) title trigram: `title % :q` + `similarity(title, :q)`
  - (B) title ILIKE: `title ILIKE %term%` (keywords 기반)
  - (C) (옵션) 페이지 본문(text) FTS/ILIKE (이번 작업은 최소 구현만, 성능 위험 크면 제외)

2) **(옵션) Vector rerank**
- 후보 page_id 범위 내에서만 `wiki_chunks.embedding IS NOT NULL`인 청크를 대상으로 vector 거리 계산
- vector 결과가 없으면 lexical 기반 chunk ranking으로 fallback

3) **Window pack**
- top chunk 기준으로 `window` 범위의 인접 청크를 묶어 context 생성

---

## embed_missing 정책(중요)
- embed_missing은 “검색할 때마다 다 임베딩”이 아니라:
  - **(Lexical로 뽑힌 후보 page들만)** 대상으로
  - embedding NULL 청크를 **최대 N개(cap)** 만큼만
  - 배치로 embed → DB update
- 기본 cap 제안:
  - `EMBED_MISSING_CAP=300` (env로 조절 가능)
  - batch size 16~64

---

## 구현 작업 목록(순서대로)
### Task 0) 공통 Core Retriever 만들기(중복 제거)
- 새 파일 생성(권장):
  - `/app/app/services/wiki_retriever.py`
- 함수 시그니처 예시:
  ```python
  def retrieve_wiki_hits(
      db: Session,
      question: str,
      top_k: int,
      window: int,
      page_limit: int,
      embed_missing: bool,
      max_chars: int | None = None,
      page_ids: list[int] | None = None,
  ) -> dict:
      \"\"\"
      return {
        "question": ...,
        "candidates": [{"page_id":..,"title":..,"score":..}],
        "hits": [{"page_id":..,"title":..,"chunk_id":..,"chunk_idx":..,"content":..,"snippet":..,"dist":..,"lex_score":..}],
        "context": "...",           # optional
        "updated_embeddings": int,  # optional
        "debug": {...}              # optional
      }
      \"\"\"
  ```
- `/api/wiki/search`와 `/api/rag/wiki/search` 둘 다 이 함수를 호출하도록 수정.

---

### Task 1) Lexical 후보 페이지 쿼리(반드시 구현)
#### 1-A) trigram + similarity 기반 (title)
- 인덱스는 이미 생성됨:
  - `wiki_pages_title_trgm` (GIN title gin_trgm_ops)
- SQL 예시:
  ```sql
  SELECT page_id, title, similarity(title, :q) AS sim
  FROM wiki_pages
  WHERE title % :q
  ORDER BY sim DESC
  LIMIT :page_limit;
  ```
- trigram 결과가 0이면 fallback으로 ILIKE:
  ```sql
  SELECT page_id, title, 0.0 AS sim
  FROM wiki_pages
  WHERE title ILIKE '%' || :q || '%'
  LIMIT :page_limit;
  ```

#### 1-B) keywords 기반(any keyword)
- keywords는 `extract_keywords(question)` 사용하되,
  - 길이 1, 조사/의미없는 토큰 제거 필터 추가(최소: len<2 제외)
- SQL 예시(ANY):
  ```sql
  SELECT page_id, title
  FROM wiki_pages
  WHERE (
    title ILIKE '%' || :k1 || '%'
    OR title ILIKE '%' || :k2 || '%'
    OR ...
  )
  LIMIT :page_limit;
  ```

> **중요:** 후보 페이지가 0이면 응답에 candidates=[]로 남기되, debug에 “lexical_miss=true” 표시.

---

### Task 2) 후보 page_id에 대해 chunk 후보 만들기
#### 2-A) Vector chunk search (가능하면)
- 후보 page_ids 내에서 embedding 있는 청크만:
  ```sql
  SELECT c.chunk_id, c.page_id, c.chunk_idx, c.content, p.title,
         (c.embedding <=> :qvec) AS dist
  FROM wiki_chunks c
  JOIN wiki_pages p ON p.page_id=c.page_id
  WHERE c.page_id = ANY(:page_ids)
    AND c.embedding IS NOT NULL
  ORDER BY dist ASC
  LIMIT :top_k;
  ```
- 여기서 qvec는 `vector_literal(embed_text(question))` 같은 형태로 전달.

#### 2-B) Fallback lexical chunk ranking (embedding이 없을 때)
- 최소 구현:
  - 후보 page_ids의 chunks 일부를 가져온 뒤(Python에서)
  - keywords 출현 기반 score 계산해서 top_k 추림
- SQL은 페이지별 chunk를 전부 가져오면 너무 큼 → 페이지별 상한 필요:
  - 예: 각 page당 chunk 50개까지만 가져오기 (chunk_idx 순)
  - 또는 `LIMIT page_limit * per_page_chunk_cap`

> 추천: “candidate_pages가 적을 때만” lexical chunk 스캔 수행.
> 예: `page_limit<=20` 일 때만 page별 80 chunks 스캔.

---

### Task 3) Window pack 생성
- top hit들의 `(page_id, chunk_idx)`를 기준으로 주변 청크를 묶음:
  ```sql
  SELECT chunk_id, page_id, chunk_idx, content, section
  FROM wiki_chunks
  WHERE page_id=:pid AND chunk_idx BETWEEN :lo AND :hi
  ORDER BY chunk_idx;
  ```
- 중복 청크 제거(여러 hit window가 겹칠 수 있음).
- snippet은 hit chunk content에서 앞부분 or 하이라이트(간단히 substring)로 생성.

---

### Task 4) embed_missing 캐시(캡 필수)
- embed_missing=true일 때만 실행.
- 후보 page_ids의 embedding NULL chunk를 찾고, 최대 cap만 업데이트:
  ```sql
  SELECT chunk_id, content
  FROM wiki_chunks
  WHERE page_id = ANY(:page_ids)
    AND embedding IS NULL
  ORDER BY page_id, chunk_idx
  LIMIT :cap;
  ```
- embed API 호출은 배치로:
  - `embed_text(list_of_texts)` 지원 여부 확인(현재 Ollama /api/embed는 input array 지원됨)
- 업데이트:
  ```sql
  UPDATE wiki_chunks
  SET embedding = :vec
  WHERE chunk_id = :chunk_id;
  ```
- 반환값: `updated_embeddings`에 업데이트 count 포함.

---

## API 수정 지시
### A) `/api/wiki/search` (app/api/wiki.py)
- 기존 `vector_search_with_window` 호출 제거하고 `retrieve_wiki_hits` 호출로 교체
- 응답 스키마는 기존 유지:
  - `question`, `candidates`, `hits`
- debug 추가는 response_model 변경 없이 로그로만 남기거나, 옵션으로만 포함.

### B) `/api/rag/wiki/search` (app/api/rag.py)
- `retrieve_wiki_context` 내부를 `retrieve_wiki_hits` 기반으로 재구성:
  - `sources = hits` 기반으로 구성
  - `context`는 window pack의 content를 이어붙인 것 사용
- 핵심: 두 엔드포인트가 **동일한 후보 생성/랭킹 로직**을 공유해야 함.

---

## 테스트 플랜(WSL + Docker 명령어)
### 1) DB 기본 확인
```bash
docker exec -i olala-db psql -U postgres -d olala -P pager=off -c \
"SELECT COUNT(*) total, COUNT(*) FILTER (WHERE embedding IS NOT NULL) embedded FROM wiki_chunks;"
```

### 2) 후보 페이지 lexical이 제대로 잡히는지(직접 SQL)
```bash
docker exec -i olala-db psql -U postgres -d olala -P pager=off -c \
"SELECT page_id, title, similarity(title,'대한민국 대통령') sim
 FROM wiki_pages
 WHERE title % '대한민국 대통령'
 ORDER BY sim DESC
 LIMIT 10;"
```

### 3) API: keyword-search (title 기반)
```bash
curl -sS -X POST http://localhost:8000/api/wiki/keyword-search \
  -H 'Content-Type: application/json' \
  -d '{"query":"대한민국 대통령","limit":10}' | jq
```

### 4) API: wiki/search (하이브리드가 되면 무조건 관련 결과가 나와야 함)
```bash
curl -sS -X POST http://localhost:8000/api/wiki/search \
  -H 'Content-Type: application/json' \
  -d '{"question":"대한민국 대통령","top_k":6,"window":2,"page_limit":8,"embed_missing":false}' | jq
```
**기대:** candidates/hits에 `대한민국 대통령(page_id=2342)`가 포함되거나, 최소한 대통령 관련 페이지가 상위로 등장.

### 5) API: rag/wiki/search (sources/context 구성 확인)
```bash
curl -sS -X POST http://localhost:8000/api/rag/wiki/search \
  -H 'Content-Type: application/json' \
  -d '{"question":"대한민국 대통령","top_k":6,"window":2,"page_ids":[2342]}' | jq
```

### 6) embed_missing 캡 동작 확인(폭주 방지)
```bash
curl -sS -X POST http://localhost:8000/api/wiki/search \
  -H 'Content-Type: application/json' \
  -d '{"question":"대한민국 대통령","top_k":6,"window":2,"page_limit":8,"embed_missing":true}' | jq
```
**기대:** updated_embeddings가 cap 이하로만 증가(로그/응답으로 확인).

---

## 성능/안정성 가드레일
- 후보 페이지 수(`page_limit`)는 기본 8~20 사이 권장.
- embed_missing cap은 기본 300 정도 권장.
- lexical chunk fallback은 page_limit이 작을 때만 수행(폭주 방지).
- SQLAlchemy raw SQL 실행은 `sqlalchemy.text()`로 감싸기(SQLAlchemy 2.x).

---

## 체크리스트(리뷰 기준)
- [ ] `/api/wiki/search`와 `/api/rag/wiki/search`가 동일한 retriever core를 사용한다.
- [ ] embedding이 0인 페이지/청크만 있어도 “관련” 결과가 나온다(lexical fallback).
- [ ] embed_missing이 쿼리마다 대량 업데이트하지 않는다(cap 적용).
- [ ] 후보/히트가 비었을 때 디버깅 가능한 로그/메타가 남는다.
- [ ] 불필요한 오래된 import (`app.db.repo`)가 남지 않는다.

---
끝.
