# Backend Architecture Analysis - Gateway & LangGraph 냉정한 분석

## 개요
현재 구조를 gateway와 LangGraph 관점에서 **냉정하고 비판적으로** 분석한 결과입니다. OLaLa 프로젝트의 백엔드는 진실성 검증 파이프라인을 구현하고 있으며, FastAPI + LangGraph + PostgreSQL 스택을 사용합니다.

---

## 🔴 심각한 구조적 문제점

### 1. Gateway 레이어의 책임 혼란 (Critical)

**문제점:**
- `app/gateway/service.py`가 진짜 게이트웨이가 아니라 **오케스트레이션 로직**을 담고 있음
- `app/gateway/database/gateway.py`도 존재하여 Gateway 개념이 두 곳에 분산
- Gateway라는 이름이 혼용되어 아키텍처 의도를 파악하기 어려움

**현재 구조:**
```
app/gateway/
├── service.py              # 실제로는 Pipeline Orchestrator
├── stage_manager.py        # Stage Registry/Facade
├── database/
│   └── gateway.py         # DB Gateway (또 다른 Gateway)
└── schemas/               # Domain schemas
```

**문제:**
1. `service.py`는 이름과 다르게 LangGraph 실행, SSE 스트리밍, 응답 빌딩을 모두 처리
2. `stage_manager.py`는 단순 Registry인데 Gateway 폴더 안에 존재
3. `database/gateway.py`는 Repository Factory인데 Gateway라고 명명
4. **Gateway 패턴이 과용**되어 실제 책임이 모호함

**영향:**
- 신규 개발자가 코드 흐름을 이해하는데 필요 이상의 시간 소요
- 테스트 작성 시 mock 포인트를 찾기 어려움
- 책임 분리가 불명확하여 변경 시 영향 범위 예측 어려움

---

### 2. LangGraph State Management의 Type Safety 부재 (Critical)

**문제점:**
- `GraphState` (TypedDict)를 정의했지만 실제 런타임에서는 `Dict[str, Any]` 사용
- LangGraph의 type 안정성을 활용하지 못하고 있음

**증거:**
```python
# app/graph/state.py - TypedDict 정의는 잘 되어 있음
class GraphState(TypedDict, total=False):
    trace_id: str
    claim_text: str
    # ... 50+ fields

# app/graph/graph.py - 실제로는 Dict[str, Any] 사용
def _run_stage(stage_name: str):
    def _runner(state: Dict[str, Any]) -> Dict[str, Any]:  # ❌ Type safety 포기
        return run_stage(stage_name, state)

# app/gateway/service.py - State 초기화도 Dict
state: Dict[str, Any] = {  # ❌ GraphState 타입 안 씀
    "trace_id": str(uuid.uuid4()),
    ...
}
```

**문제:**
1. IDE 자동완성/타입 체크 불가능
2. 런타임에만 KeyError 발생 (개발 단계에서 못 잡음)
3. State 필드 의존성을 코드 리뷰로만 파악 가능
4. Refactoring 시 영향 범위 추적 불가

**실제 리스크:**
- `state.get("cliam_text")` 같은 오타가 런타임까지 발견 안 됨
- Stage 간 필수 필드 누락 시 파이프라인 중간에 크래시

---

### 3. Stage 구현의 일관성 부재 (High)

**문제점:**
Stage들이 동기/비동기를 섞어 쓰며, 에러 처리 패턴도 제각각

**현재 상황:**

| Stage | 실행 방식 | Async 지원 | Error Handling |
|-------|----------|-----------|----------------|
| stage01_normalize | Sync | ❌ | Try-catch with fallback |
| stage02_querygen | Sync | ❌ | Try-catch |
| stage03_collect | **Sync wrapper of async** | ✅ | Timeout wrapping |
| stage04_score | Sync | ❌ | Basic |
| stage06_verify_support | Sync | ❌ | Try-catch |

**코드 증거:**
```python
# stage03_collect/node.py
async def run_wiki_async(state: dict):
    # 진짜 async 구현
    ...

def run_wiki(state: dict):
    # Sync wrapper
    return asyncio.run(run_wiki_async(state))  # ❌ 이벤트 루프 충돌 위험

# app/graph/graph.py
def _async_node_wrapper(stage_name: str):
    async def _async_runner(state: Dict[str, Any]) -> Dict[str, Any]:
        fn = _with_log(stage_name, _run_stage(stage_name))
        return await asyncio.to_thread(fn, state)  # ❌ Sync를 Thread에서 실행
    return _async_runner
```

**문제:**
1. `asyncio.run()` 호출이 이미 실행 중인 이벤트 루프와 충돌
2. Thread pool로 우회하지만 진짜 병렬성 없음 (GIL)
3. Stage마다 다른 패턴이라 코드 읽기 힘듦

---

### 4. LangGraph 활용도 낮음 (High)

**문제점:**
LangGraph를 쓰지만 핵심 기능을 거의 활용하지 않음

**활용하지 않는 기능:**
- ✅ **사용함**: StateGraph, Node, Edge, Conditional edges (일부)
- ❌ **안 씀**: Checkpointing (재개 가능성)
- ❌ **안 씀**: Human-in-the-loop
- ❌ **안 씀**: Subgraph (모듈화)
- ❌ **안 씀**: Tool calling integration
- ❌ **안 씀**: Streaming events (Custom stream 직접 구현)

**현재 구현:**
```python
# app/graph/graph.py - 단순 Linear Pipeline
graph.set_entry_point("stage01_normalize")
graph.add_edge("stage01_normalize", "stage02_querygen")
graph.add_edge("stage02_querygen", "adapter_queries")
# ... 모두 linear edges

# Parallelism도 단순 fan-out/fan-in
graph.add_edge("adapter_queries", "stage03_wiki")
graph.add_edge("adapter_queries", "stage03_web")
graph.add_edge("stage03_wiki", "stage03_merge")
graph.add_edge("stage03_web", "stage03_merge")
```

**문제:**
1. Linear pipeline이면 LangGraph 없이 for문으로도 가능
2. Checkpointing 없어서 중간 실패 시 처음부터 다시 실행
3. 복잡도 대비 얻는 가치가 낮음

**대안 고려 필요:**
- 단순 pipeline → `celery` + DAG만으로도 충분
- 또는 LangGraph의 고급 기능을 제대로 활용

---

### 5. 동기/비동기 실행 경로 이중화 (Medium-High)

**문제점:**
`run_pipeline` (동기)와 `run_pipeline_stream` (비동기) 두 경로가 존재하지만 **핵심 로직이 중복**됨

**코드 증거:**
```python
# app/gateway/service.py
def run_pipeline(req: TruthCheckRequest) -> TruthCheckResponse:
    # 동기 실행
    state: Dict[str, Any] = {
        "trace_id": str(uuid.uuid4()),
        "input_type": req.input_type,
        # ... state 초기화 (중복 1)
    }
    out = run_stage_sequence(state, req.start_stage, req.end_stage)
    return _build_response(out, state["trace_id"])

async def run_pipeline_stream(req: TruthCheckRequest):
    # 비동기 실행
    state: Dict[str, Any] = {
        "trace_id": str(uuid.uuid4()),
        "input_type": req.input_type,
        # ... state 초기화 (중복 2)
    }
    async for output in app.astream(state):
        # Stream 처리
```

**중복된 코드:**
1. State 초기화 로직
2. `_build_response` 호출 로직
3. Stage 진행 모니터링 로직 (로그)

**문제:**
- State 초기화 로직 변경 시 두 곳 수정 필요
- 버그 수정 시 한 쪽만 고치는 실수 가능
- 동기/비동기 결과 불일치 위험

---

### 6. 에러 처리의 불완전성 (High)

**문제점:**
에러 처리가 Stage마다, Layer마다 다르고 일부는 누락됨

**Layer별 에러 처리:**

| Layer | Error Handling | Recovery |
|-------|---------------|----------|
| API (`truth_check.py`) | ❌ None | FastAPI default |
| Gateway (`service.py`) | ✅ Try-catch | Fallback to error response |
| LangGraph Nodes | **제각각** | Stage dependent |
| Stage implementations | ✅ Mostly | Varying quality |
| External API calls | **불완전** | Timeout only |

**위험한 코드:**
```python
# app/stages/stage03_collect/node.py
def _search_naver(query: str):
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        # ❌ API 응답 형식 검증 없음
        items = data["items"]  # KeyError 가능
```

```python
# app/gateway/service.py
async for output in app.astream(state):
    # ❌ LangGraph 내부 Stage 에러가 여기서 처리 안 됨
    for node_name, node_state in output.items():
        # Stage 내부 예외는 여기까지 안 올라옴
```

**문제:**
1. External API (Naver, DDG, Wiki) 호출 실패 시 전체 파이프라인 크래시
2. 부분 실패 복구 메커니즘 없음
3. 에러 로깅은 있지만 metric/monitoring 없음

---

### 7. Database 접근 패턴의 혼재 (Medium)

**문제점:**
DB 접근이 여러 패턴으로 혼재되어 있음

**패턴들:**
1. **Direct SessionLocal** (Legacy)
   ```python
   # app/stages/stage03_collect/node.py
   from app.db.session import SessionLocal
   
   def _search_wiki(...):
       db = SessionLocal()
       try:
           hits = retrieve_wiki_hits(db, ...)
       finally:
           db.close()
   ```

2. **FastAPI Dependency Injection**
   ```python
   # app/api/rag.py
   def wiki_search(req: WikiSearchRequest, db: Session = Depends(get_db)):
       pack = retrieve_wiki_context(db, ...)
   ```

3. **Gateway Pattern** (존재하지만 안 씀)
   ```python
   # app/gateway/database/gateway.py
   class DatabaseGateway:  # ❌ 실제로 안 쓰임
       @contextmanager
       def session(self) -> Generator[Session, None, None]:
           ...
   ```

**문제:**
- SessionLocal 직접 호출은 connection pool 관리 위험
- Pattern 통일 안 되어 Transaction boundary 파악 어려움
- Testing 시 DB mocking 포인트가 여러 곳

---

### 8. Logging과 Observability 부족 (Medium)

**문제점:**
로그는 많지만 구조화/집계가 안 되어 있어 **운영 가시성이 낮음**

**현재 로깅:**
```python
# app/graph/stage_logger.py
def attach_stage_log(state, stage_name, out, started_at=None):
    # ✅ Stage logs는 있음
    state.setdefault("stage_logs", []).append({
        "stage": stage_name,
        "status": "success",
        "elapsed_ms": elapsed,
    })
```

**부족한 것:**
1. **Metric 수집 없음**
   - Stage별 latency P50/P95/P99
   - Error rate
   - LLM token usage
   
2. **Trace context 불완전**
   - `trace_id`는 있지만 log aggregation 시스템 연동 없음
   - 분산 추적 불가 (OpenTelemetry 등 미사용)

3. **Alert 메커니즘 없음**
   - Pipeline 실패 시 알림 없음
   - SLA 위반 감지 불가

---

### 9. Schema 중복과 변환 오버헤드 (Medium)

**문제점:**
여러 Schema 레이어가 존재하여 변환 비용이 높음

**Schema Layers:**
```
Request → GraphState → Stage Outputs → Gateway Schemas → Response
    ↓          ↓              ↓               ↓              ↓
TruthCheck  Dict[str,Any]  Various      Evidence/       TruthCheck
Request                    Dicts        Verdict         Response
```

**변환 지점:**
1. `TruthCheckRequest` → `GraphState` dict
2. Stage 출력 → `gateway/schemas` (Evidence, Verdict 등)
3. Gateway schemas → `TruthCheckResponse`

**코드:**
```python
# app/gateway/service.py - _build_response
def _build_response(out: Dict[str, Any], trace_id: str) -> TruthCheckResponse:
    # ❌ 60줄짜리 변환 로직
    final_verdict = out.get("final_verdict") if isinstance(...) else None
    if final_verdict:
        label = final_verdict.get("label", "UNVERIFIED")
        # ... 30+ lines of mapping
    
    citations = [
        Citation(
            source_type=_map_source_type(c.get("source_type")),
            # ... more mapping
        )
        for c in citation_source
    ]
```

**문제:**
- 변환 로직이 복잡하고 버그 가능성 높음
- Schema 변경 시 여러 곳 수정 필요
- Runtime 타입 검증이 없어서 필드 누락/오타 위험

---

### 10. Adapter Pattern의 불명확함 (Low-Medium)

**문제점:**
`adapter_queries` 노드가 왜 필요한지, 왜 Graph에 노드로 들어갔는지 불명확

**코드:**
```python
# app/graph/graph.py
def _build_queries(state: Dict[str, Any]) -> Dict[str, Any]:
    # Stage02 출력을 받아 search_queries 생성
    variants = state.get("query_variants", []) or []
    # ... 70줄의 변환 로직
    return {"search_queries": search_queries}

graph.add_node("adapter_queries", _async_adapter_wrapper())
```

**문제:**
1. 단순 데이터 변환인데 **LangGraph Node로** 추가
2. Stage02와 Stage03 사이에 끼워진 이유가 불명확
3. Streaming에서 특수 처리됨 (buffering)

**의문:**
- 이것은 Stage02의 후처리 아닌가?
- 왜 독립 노드여야 하는가?
- Graph 구조를 복잡하게 만드는 것 대비 가치가 있는가?

---

### 11. Configuration Management 부재 (Medium)

**문제점:**
환경변수가 각 모듈에 흩어져 있고 중앙 관리가 없음

**현재:**
```python
# app/stages/_shared/slm_client.py
SLM1_BASE_URL = os.getenv("SLM1_BASE_URL", "http://localhost:8080/v1")
SLM2_BASE_URL = os.getenv("SLM2_BASE_URL", ...)
JUDGE_BASE_URL = os.getenv("JUDGE_BASE_URL", ...)

# app/services/wiki_usecase.py
WIKI_EMBEDDINGS_READY = os.getenv("WIKI_EMBEDDINGS_READY", "")

# app/api/rag.py
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
```

**문제:**
1. 설정이 코드 곳곳에 흩어져 있음
2. 기본값이 중복 정의됨 (불일치 위험)
3. Pydantic Settings 같은 검증 메커니즘 없음
4. 실행 시점에만 missing env 발견

---

### 12. Test Coverage 불명확 (Medium)

**발견된 테스트:**
```
backend/tests/
├── __init__.py
└── verify_scoring.py
```

**문제:**
1. Integration test가 **1개**밖에 없음
2. Stage 단위 테스트 없음
3. Gateway, LangGraph orchestration 테스트 없음
4. Mocking strategy 불명확

---

## 🟡 개선이 필요한 부분

### 13. Prompt 관리 방식 (Low-Medium)

**현재:**
```python
# app/stages/stage01_normalize/node.py
PROMPT_FILE = Path(__file__).parent / "prompt_normalize.txt"

@lru_cache
def load_system_prompt():
    with PROMPT_FILE.open(encoding="utf-8") as f:
        return f.read()
```

**문제:**
- Prompt versioning 없음
- A/B testing 불가
- Prompt 변경 시 코드 재배포 필요
- LLMOps 도구 (LangSmith, Helicone 등) 미연동

---

### 14. External API Rate Limiting 없음 (Medium)

**문제점:**
Naver, DuckDuckGo API 호출에 rate limiting이 없음

**코드:**
```python
# app/stages/stage03_collect/node.py
async def run_web_async(state: dict):
    tasks = []
    for query in queries:
        if query.get("type") == "news":
            tasks.append(_safe_execute(_search_naver(query["text"])))
        else:
            tasks.append(_safe_execute(_search_duckduckgo(query["text"])))
    
    # ❌ 동시 요청 제한 없음
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

**위험:**
- API quota 초과 시 전체 서비스 차단
- 429 Too Many Requests 처리 없음

---

### 15. Wiki Search 로직의 복잡도 (Low)

**관찰:**
`wiki_usecase.py`가 400줄이 넘고 하나의 함수(`retrieve_wiki_hits`)가 250줄

**구조:**
```python
def retrieve_wiki_hits(
    db: Session,
    question: str,
    top_k: int = 8,
    window: int = 2,
    page_limit: int = 8,
    embed_missing: bool = False,
    max_chars: Optional[int] = None,
    page_ids: Optional[List[int]] = None,
    search_mode: str = "auto",
):
    # 250 lines of:
    # - Keyword extraction
    # - FTS search
    # - Vector search
    # - Hybrid reranking
    # - Context window expansion
    # - Deduplication
```

**문제:**
- Single Responsibility Principle 위반
- Unit test 불가능
- 로직 이해/수정 어려움

---

## 📋 개선 우선순위별 액션 플랜

### 🔴 Priority 1: Critical (즉시 수정 필요)

#### 1.1 Gateway 책임 재정의
**목표:** Gateway 개념 통일 및 명확한 책임 분리

**변경사항:**
```
기존:
app/gateway/
├── service.py (실제 orchestrator)
├── stage_manager.py (registry)
└── database/gateway.py (repo factory)

제안:
app/
├── orchestrator/
│   ├── pipeline.py (run_pipeline 이동)
│   └── streaming.py (run_pipeline_stream 이동)
├── stages/
│   └── registry.py (stage_manager 이동)
└── infrastructure/
    └── database/
        ├── session.py
        └── repositories/
```

**작업:**
1. `gateway/service.py` → `orchestrator/pipeline.py` + `streaming.py`로 분리
2. `gateway/stage_manager.py` → `stages/registry.py`로 이동
3. `gateway/database/` → `infrastructure/database/`로 이동
4. Old imports 업데이트 (100+ files 예상)

**예상 작업량:** 2-3 days

---

#### 1.2 GraphState Type Safety 강화
**목표:** TypedDict를 실제로 활용하여 type safety 확보

**변경사항:**
```python
# Before
def _run_stage(stage_name: str):
    def _runner(state: Dict[str, Any]) -> Dict[str, Any]:
        return run_stage(stage_name, state)

# After
from app.graph.state import GraphState

def _run_stage(stage_name: str):
    def _runner(state: GraphState) -> GraphState:
        return run_stage(stage_name, state)

# Stage signatures 통일
def run(state: GraphState) -> GraphState:
    # All stages follow this
```

**작업:**
1. 모든 Stage의 `run()` signature를 `GraphState` → `GraphState`로 변경
2. `stage_manager.py`의 `StageFn` 타입 업데이트
3. Runtime validator 추가 (Pydantic v2 TypeAdapter 활용)
4. Mypy strict mode 적용 및 타입 에러 수정

**예상 작업량:** 3-4 days

---

#### 1.3 에러 처리 통일
**목표:** 일관된 에러 처리 및 부분 실패 복구

**변경사항:**
```python
# app/infrastructure/errors.py
class PipelineError(Exception):
    """Base exception for pipeline errors."""
    def __init__(self, stage: str, message: str, recoverable: bool = False):
        self.stage = stage
        self.message = message
        self.recoverable = recoverable

class ExternalAPIError(PipelineError):
    """External API call failures."""
    pass

# app/orchestrator/error_handler.py
class ErrorHandler:
    def handle_stage_error(self, error: PipelineError, state: GraphState) -> GraphState:
        if error.recoverable:
            # Add risk flag and continue
            state["risk_flags"].append(f"{error.stage}_PARTIAL_FAILURE")
            return state
        else:
            # Fail fast
            raise error

# All stages
def run(state: GraphState) -> GraphState:
    try:
        result = do_work(state)
        return result
    except ExternalAPIError as e:
        raise PipelineError(
            stage="stage03_collect",
            message=str(e),
            recoverable=True
        )
```

**작업:**
1. Error hierarchy 정의
2. Stage별 에러 처리 리팩토링 (9 stages)
3. Orchestrator에 ErrorHandler 통합
4. External API wrapper with retry/circuit breaker

**예상 작업량:** 4-5 days

---

### 🟡 Priority 2: High (1-2주 내 처리)

#### 2.1 LangGraph 활용 개선 또는 제거 결정

**옵션 A: LangGraph 제대로 활용**
```python
# Checkpointing 추가
from langgraph.checkpoint.sqlite import SqliteSaver

memory = SqliteSaver.from_conn_string("checkpoints.db")
app = graph.compile(checkpointer=memory)

# 중간 재개 가능
result = await app.ainvoke(state, config={"configurable": {"thread_id": trace_id}})
```

**작업:**
- Checkpointing 추가
- Human-in-the-loop 노드 (Stage06, 07에서 사용자 확인)
- Conditional routing (빠른 경로 vs 정밀 경로)

**옵션 B: 단순화**
```python
# Celery + 간단한 DAG로 대체
from celery import chain, group

pipeline = chain(
    stage01_normalize.s(),
    stage02_querygen.s(),
    group(stage03_wiki.s(), stage03_web.s()),
    stage03_merge.s(),
    # ...
)
```

**작업:**
- LangGraph 제거
- Celery task 정의
- Redis/RabbitMQ 인프라 추가

**결정 기준:**
- 향후 Human-in-the-loop 필요성
- Checkpointing/재개 요구사항
- 팀의 Celery 경험

**예상 작업량:** 5-7 days (옵션 선택 후)

---

#### 2.2 Stage 동기/비동기 통일

**목표:** 모든 Stage를 진짜 async로 변환

**변경사항:**
```python
# All stages
async def run(state: GraphState) -> GraphState:
    # Truly async implementation
    async with httpx.AsyncClient() as client:
        response = await client.get(...)
    return state

# 외부 blocking call (DB, Ollama) 처리
async def run(state: GraphState) -> GraphState:
    # DB는 asyncpg 사용
    async with async_session() as db:
        results = await db.execute(query)
    
    # LLM 호출은 httpx async
    async with httpx.AsyncClient() as client:
        response = await client.post(ollama_url, ...)
```

**작업:**
1. SQLAlchemy → asyncpg migration (또는 SQLAlchemy 2.0 async)
2. requests → httpx async migration
3. 모든 Stage를 native async로 변환
4. `asyncio.run()` 제거

**예상 작업량:** 7-10 days

---

#### 2.3 동기/비동기 실행 경로 통합

**목표:** 중복 제거

**변경사항:**
```python
# Unified state initialization
def _init_state(req: TruthCheckRequest) -> GraphState:
    return {
        "trace_id": str(uuid.uuid4()),
        "input_type": req.input_type,
        # ... 한 곳에서만 정의
    }

# Sync wrapper
def run_pipeline(req: TruthCheckRequest) -> TruthCheckResponse:
    return asyncio.run(run_pipeline_async(req))

# Main async implementation
async def run_pipeline_async(req: TruthCheckRequest) -> TruthCheckResponse:
    state = _init_state(req)
    result = await app.ainvoke(state)
    return _build_response(result, state["trace_id"])

# Streaming
async def run_pipeline_stream(req: TruthCheckRequest):
    state = _init_state(req)  # 같은 함수 사용
    async for output in app.astream(state):
        yield ...
```

**예상 작업량:** 2-3 days

---

### 🟢 Priority 3: Medium (1개월 내)

#### 3.1 Configuration Management 중앙화

**변경사항:**
```python
# app/infrastructure/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    postgres_db: str
    postgres_user: str
    postgres_password: str
    database_url: str
    
    # LLM
    slm1_base_url: str
    slm1_model: str
    slm1_max_tokens: int = 2000
    
    # External APIs
    naver_client_id: str
    naver_client_secret: str
    
    # Features
    wiki_embeddings_ready: bool = False
    
    class Config:
        env_file = ".env"

settings = Settings()

# 사용
from app.infrastructure.config import settings

client = SLMClient(settings.slm1_base_url, settings.slm1_model)
```

**예상 작업량:** 2-3 days

---

#### 3.2 Database 접근 패턴 통일

**변경사항:**
```python
# 모두 Dependency Injection으로 통일
# app/infrastructure/database/dependencies.py
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

# Stage에서 사용
async def run(state: GraphState, db: AsyncSession = Depends(get_async_db)) -> GraphState:
    results = await wiki_repo.search(db, query)
```

**작업:**
1. Direct SessionLocal 제거
2. DI pattern으로 통일
3. Stage에 db injection (LangGraph config로 전달)

**예상 작업량:** 3-4 days

---

#### 3.3 Observability 추가

**변경사항:**
```python
# OpenTelemetry 추가
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider

tracer = trace.get_tracer(__name__)

# Stage에서 사용
async def run(state: GraphState) -> GraphState:
    with tracer.start_as_current_span("stage01_normalize") as span:
        span.set_attribute("trace_id", state["trace_id"])
        # ... work
        span.set_attribute("claim_length", len(claim))
```

**Metrics:**
```python
from prometheus_client import Histogram, Counter

stage_latency = Histogram("stage_latency_seconds", "Stage latency", ["stage"])
stage_errors = Counter("stage_errors_total", "Stage errors", ["stage", "error_type"])

@stage_latency.labels(stage="stage01").time()
async def run(state: GraphState) -> GraphState:
    # ...
```

**예상 작업량:** 4-5 days

---

#### 3.4 Schema 변환 단순화

**변경사항:**
```python
# GraphState를 Pydantic model로
from pydantic import BaseModel

class GraphState(BaseModel):
    trace_id: str
    claim_text: str | None = None
    # ... all fields with validation
    
    model_config = ConfigDict(extra="allow")

# 변환 최소화
def _build_response(state: GraphState) -> TruthCheckResponse:
    # Direct field mapping (Pydantic to Pydantic)
    return TruthCheckResponse(
        analysis_id=state.trace_id,
        label=state.final_verdict.label,
        # ... 간단한 매핑
    )
```

**예상 작업량:** 3-4 days

---

### 🔵 Priority 4: Low (Long-term)

#### 4.1 Prompt Management 개선
- Prompt versioning (Git LFS 또는 DB)
- A/B testing framework
- LangSmith integration

**예상 작업량:** 5-7 days

#### 4.2 External API Rate Limiting
- aiolimiter 추가
- Circuit breaker (tenacity)

**예상 작업량:** 2-3 days

#### 4.3 Wiki Search 로직 리팩토링
- `retrieve_wiki_hits` → 여러 작은 함수로 분리
- Query 전략 패턴 적용

**예상 작업량:** 3-4 days

#### 4.4 Test Coverage 확대
- Stage 단위 테스트 (80%+ coverage)
- Integration test suite
- E2E test with real LLM

**예상 작업량:** 10-15 days

---

## 📊 총 예상 작업량

| Priority | 항목 수 | 예상 일수 |
|----------|--------|----------|
| P1 (Critical) | 3 | 9-12 days |
| P2 (High) | 3 | 14-20 days |
| P3 (Medium) | 4 | 12-16 days |
| P4 (Low) | 4 | 20-27 days |
| **Total** | **14** | **55-75 days** |

*1인 개발 기준, 병렬 작업 시 단축 가능*

---

## 🎯 권장 접근 방식

### Phase 1: Foundation (2-3주)
1. Gateway 재구조화 (P1.1)
2. Type safety 강화 (P1.2)
3. Configuration 중앙화 (P3.1)

### Phase 2: Reliability (3-4주)
4. 에러 처리 통일 (P1.3)
5. LangGraph 결정 및 적용 (P2.1)
6. 실행 경로 통합 (P2.3)

### Phase 3: Performance (2-3주)
7. Async 통일 (P2.2)
8. DB 패턴 통일 (P3.2)
9. Observability (P3.3)

### Phase 4: Quality (4-6주)
10. Schema 단순화 (P3.4)
11. Test coverage (P4.4)
12. 나머지 Low priority items

---

## 💡 즉시 적용 가능한 Quick Wins

1. **Mypy 설정 추가** (1시간)
   ```toml
   [tool.mypy]
   python_version = "3.11"
   disallow_untyped_defs = true
   ```

2. **Pre-commit hooks** (1시간)
   ```yaml
   repos:
     - repo: https://github.com/pre-commit/mirrors-mypy
       hooks:
         - id: mypy
   ```

3. **README에 Architecture Diagram 추가** (2시간)
   - Gateway vs Orchestrator 명확히
   - Data flow 시각화

4. **ENV validation 추가** (2시간)
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   
   required = ["SLM1_BASE_URL", "POSTGRES_DB", ...]
   missing = [k for k in required if not os.getenv(k)]
   if missing:
       raise RuntimeError(f"Missing: {missing}")
   ```

---

## 결론

현재 백엔드는 **기능은 작동하지만 유지보수성과 확장성에 심각한 문제**가 있습니다:

**핵심 문제:**
1. Gateway 개념 혼란 → **아키텍처 의도 불명확**
2. Type safety 부재 → **런타임 에러 위험**
3. LangGraph 저활용 → **복잡도 대비 가치 낮음**
4. 일관성 없는 패턴 → **코드 이해 비용 높음**

**권장사항:**
- **P1 항목부터 시작** (Type safety + Gateway 정리)
- LangGraph 활용도 재평가 필요
- 장기적으로 Test coverage 확보 필수

코드를 수정하지 않고 플랜만 작성한 상태이므로, **승인 후 우선순위에 따라 단계적 리팩토링** 진행 가능합니다.
