# OLaLA Wiki RAG: Candidate Rerank + “LLM 재호출 반영” Work Order (for Codex)

> 목적: **(1) 후보 페이지 랭킹을 뾰족하게 만들고**, **(2) RAG 근거가 LLM 답변 생성에 항상 반영**되도록 워크플로우를 고정한다.  
> 브랜치: `sub` 에만 작업/푸시. `main` 머지 금지.

---

## 0) 현재 증상 요약

### A. 후보는 잡히는데 우선순위가 이상함
- keyword 후보 쿼리가 `ORDER BY page_id` 형태라면, `page_limit`가 작을 때 **관련도 높은 페이지가 아닌 “page_id가 작은 페이지”가 먼저 들어가는** 문제가 생김.
- 그 결과, vector search가 올바른 page_id pool을 못 받아서 정답 페이지가 뒤로 밀림.

### B. “sources는 뽑혔는데”, LLM 답변은 근거 없이 생성되는 케이스
- 프론트에서 RAG 후보/근거는 `/api/wiki/search` 또는 `/api/rag/wiki/search`로 뽑아놓고,
- LLM 답변 생성은 별도의 proxy endpoint를 호출하는 구조면,
- **LLM 호출에 RAG context가 안 들어갈 수 있음** → “재호출 반영 안 됨”.

---

## 1) 작업 목표

### 목표 1) Candidate Rerank 강화
- 제목 정확 매칭, 키워드 포함 개수, trigram similarity 등을 이용해
- `page_limit`가 작아도 **정답 페이지가 후보 상단에 안정적으로 포함**되게 만든다.

### 목표 2) RAG → LLM 호출 경로 단일화
- RAG 토글 ON이면 **한 번의 호출로 sources + 답변 스트림**을 받게 고정한다.
- 권장: 프론트는 RAG 모드에서 `/api/wiki/rag-stream`만 호출.

---

## 2) 변경 범위(수정 대상)

> 실제 파일 경로는 repo에서 다를 수 있으니, 아래 “검색 키워드”로 먼저 정확한 파일을 찾아 수정한다.

### A. DB repo (후보 쿼리 / 정렬 로직)
- `backend/app/db/repos/rag_repo.py` (또는 기존 `app/db/repo.py` 계열)
- 수정 대상 함수(예상):
  - `find_pages_by_any_keyword(keywords, limit)`
  - `find_pages_by_title_ilike(query, limit)`
  - `find_pages_by_title_trgm(query, limit, threshold)` (있는 경우)

### B. Retriever (후보 합치기 + rerank)
- `backend/app/services/wiki_retriever.py` (또는 유사한 파일)
- 수정 대상 함수(예상):
  - `retrieve_wiki_hits(...)` / `retrieve_wiki_context(...)` 내부 candidate 생성 파트

### C. RAG API (LLM 호출 반영)
- `backend/app/api/rag.py`
  - `POST /api/rag/wiki/search`
  - `POST /api/wiki/rag-stream`

### D. Frontend (RAG 토글 시 호출 경로 고정)
- “LLM 데모 페이지” fetch/axios 코드 (파일명 불명)
  - RAG 토글 ON → `/api/wiki/rag-stream`로 호출
  - RAG 토글 OFF → 기존 LLM proxy 사용

---

## 3) 사전 확인(필수)

### 3.1 pg_trgm 확장 확인
DB에 pg_trgm이 없으면 similarity를 못 씀.

```bash
docker exec -i olala-db psql -U postgres -d olala -P pager=off -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

### 3.2 인덱스 확인
이미 생성되어 있으면 OK.

```sql
CREATE INDEX IF NOT EXISTS wiki_pages_title_trgm
ON public.wiki_pages USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS wiki_chunks_page_id_idx
ON public.wiki_chunks (page_id);
```

---

## 4) 구현 상세

## 4A) 후보 쿼리: `find_pages_by_any_keyword()` 정렬 개선 (필수)

### 문제
OR 조건으로 title ILIKE 매칭 후, **page_id로 정렬하면 관련도와 무관**.

### 해결
다음 점수를 SQL로 만들고 점수 순으로 정렬:

- `match_count`: title에 포함된 keyword 개수
- `all_in_title`: match_count == keyword 개수 (모두 포함) → 보너스
- `exact_match`: title == normalized_query (가능하면) → 최상단 보너스
- (옵션) `sim`: similarity(title, normalized_query) → 동률 깨기

#### 권장 정렬 우선순위
1) exact_match DESC  
2) all_in_title DESC  
3) match_count DESC  
4) sim DESC  
5) title_length ASC (옵션)

> `normalized_query`는 retriever에서 만든 “질문 정규화 문자열”을 repo 함수 인자로 추가해도 됨.

### 구현 가이드 (SQLAlchemy text 또는 ORM)
- match_count 예시 (Postgres):
  - `CASE WHEN title ILIKE '%키워드%' THEN 1 ELSE 0 END` 를 키워드 수만큼 합산
- all_in_title:
  - `CASE WHEN match_count = :n THEN 1 ELSE 0 END`

> Codex는 현재 구현 스타일(SQLAlchemy ORM / raw SQL) 그대로 유지하되, ORDER BY를 score 기반으로 바꾸는 게 핵심.

---

## 4B) 후보 생성: “단일 모드 확정” 제거 → 합집합 + rerank (권장)

### 문제
keyword 후보가 1개라도 있으면 거기서 끝나면, trigram/ilike 후보를 못 씀 → 후보 풀이 빈약해짐.

### 목표
- keyword / trigram / ilike 결과를 모두 모아서 **page_id로 dedup** 후
- 최종 score로 정렬해서 `page_limit`만큼 자른다.

### 점수 설계(간단 버전)
- keyword 결과:
  - `score = all_in_title*100 + match_count*10 + sim*5`
- trigram 결과:
  - `score = sim*20` (keyword 결과보다 약간 약하게)
- ilike 결과:
  - `score = 1` (fallback)

> 구현 난이도 낮고, 체감 성능이 즉시 좋아짐.

### “엔티티 우선” 핀 규칙(옵션)
- query에 특정 엔티티(예: “윤석열”)가 들어가면,
- `title == 엔티티` 페이지는 항상 후보 topN에 포함시키는 예외 규칙 추가.

---

## 4C) hit rerank: lex_score 정규화(권장)

현재 rerank가 snippet/content에서 키워드 출현 횟수만 세면,
- window가 커지거나 문서 길이가 길수록 과대평가될 수 있음.

권장:
- `lex_score = count / log(1 + len(text))` 같은 간단 정규화
- 또는 `min(count, cap)`로 cap 설정

---

## 4D) “RAG 근거가 LLM 재호출에 반영”되게 고정 (필수)

### 최우선 권장 방식: 프론트가 RAG 모드일 때 `/api/wiki/rag-stream`만 호출
- `/api/wiki/rag-stream`는 pack["context"]를 prompt에 포함해 LLM을 바로 호출한다.
- 따라서 “sources와 답변이 서로 다른 호출에서 분리되는 문제”가 사라짐.

#### Frontend 요구사항
- RAG toggle ON:
  - `POST /api/wiki/rag-stream` (NDJSON streaming)
  - 첫 줄: `{type:"sources", sources:[...]}`
  - 이후 줄: ollama stream line(JSON) 반복
- RAG toggle OFF:
  - 기존 LLM proxy 호출 유지

### 대안(차선): `/api/rag/wiki/search`가 context까지 반환
- `include_context: true`일 때 response에 `context`(string)를 포함시키고,
- 프론트/프록시가 그 context를 prompt에 포함하도록 수정.

> 단, context는 길 수 있으니 default는 false로 유지 권장.

---

## 4E) rag.py 스키마 중복 정리 (권장)
- `WikiSearchRequest`에 동일 필드가 중복 선언되어 있으면 제거한다.
  - 예: `page_limit`, `embed_missing` 중복 정의

---

## 5) 테스트 플랜 (필수)

## 5.1 Candidate 랭킹 테스트
### Query: “윤석열 탄핵”
- 기대:
  - 후보에 `윤석열`, `탄핵`, `윤석열 정부`, `탄핵` 관련 문서가 상단 포함
  - page_limit=8이어도 관련 문서가 밀리지 않음

```bash
curl -sS -X POST http://localhost:8000/api/wiki/search \
  -H 'Content-Type: application/json' \
  -d '{"question":"윤석열 탄핵","top_k":6,"window":2,"page_limit":8,"embed_missing":true}' | jq
```

## 5.2 질문형 테스트 (키워드 약한 케이스)
### Query: “윤석열은 탄핵되었어?”
- 기대:
  - 후보가 비지 않고,
  - 동일하게 “윤석열/탄핵” 관련 문서가 후보 상단 포함

```bash
curl -sS -X POST http://localhost:8000/api/wiki/search \
  -H 'Content-Type: application/json' \
  -d '{"question":"윤석열은 탄핵되었어?","top_k":6,"window":2,"page_limit":8,"embed_missing":true}' | jq
```

## 5.3 RAG-stream 단일 호출 확인
- 기대:
  - 첫 줄 sources 포함
  - 이후 LLM 스트림이 이어서 나옴
  - 프론트에서도 sources가 “No sources yet”로 남지 않음

```bash
curl -N -sS -X POST http://localhost:8000/api/wiki/rag-stream \
  -H 'Content-Type: application/json' \
  -d '{"question":"현재 대한민국 대통령은??","top_k":6,"window":2,"max_chars":4200}' \
  | sed -n '1,20p'
```

> NOTE: `head`로 끊으면 `curl: (18)` 경고는 정상(파이프가 먼저 닫혀서).

---

## 6) 완료 조건 (Acceptance Criteria)

1) `page_limit=8`에서도 “윤석열 탄핵”, “윤석열은 탄핵되었어?” 같은 케이스에서
   - 후보가 비지 않고
   - 정답 문서군이 후보 상단에 들어간다.

2) RAG 토글 ON일 때
   - sources가 UI에 표시되고
   - LLM 답변이 해당 sources/context를 반영한다(=근거 없이 말하지 않음).

3) `rag.py` request schema 중복이 제거되어 혼동이 없다.

4) 변경은 `sub` 브랜치에만 커밋/푸시.

---

## 7) Codex 실행 지시(정확히)

1) 아래 명령으로 수정 대상 파일을 먼저 찾아라.
```bash
grep -R "find_pages_by_any_keyword" -n backend/app | head -n 20
grep -R "retrieve_wiki" -n backend/app/services backend/app/db | head -n 50
grep -R "rag-stream" -n backend/app | head -n 50
```

2) **repo 후보 쿼리 정렬을 score 기반으로 수정**한다.  
3) **retriever에서 후보를 합집합으로 모아 rerank**한다.  
4) **프론트 RAG 토글 ON 시 `/api/wiki/rag-stream`로 고정**한다.  
5) 테스트 플랜을 그대로 실행해 결과를 캡쳐/로그로 남긴다.  
6) 커밋 메시지:
   - `feat(rag): sharpen wiki candidate ranking and bind RAG context to LLM`
