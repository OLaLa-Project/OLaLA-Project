# Backend Refactoring Roadmap (구체적 실행 계획)

> 작성일: 2026-02-06  
> 기반: backend-architecture-analysis.md  
> 목적: 우선순위별 구체적 작업 지시서

---

## 📌 전체 로드맵 요약

### 병렬 작업 가능 트랙
```
Track A (Foundation): P1.1, P1.2, P3.1 → P3.2
Track B (Reliability): P1.3 → P2.3 → P4.2
Track C (LangGraph): P2.1 (독립 결정 후 진행)
Track D (Performance): P2.2 (Track A 완료 후)
```

### 예상 타임라인 (2인 작업 기준)
- **Week 1-2**: Foundation (P1.1, P1.2, P3.1)
- **Week 3-4**: Reliability (P1.3, P2.3)
- **Week 5-6**: Performance (P2.2, P3.2)
- **Week 7-8**: Quality (P3.3, P3.4)
- **Week 9+**: Long-term items (P4.x)

---

## 🔴 Priority 1: Critical

### P1.1 Gateway 책임 재정의 및 폴더 구조 개편

#### 목표
Gateway 개념 통일, 명확한Layer 분리

#### 변경 대상 파일 (상세)

##### 1. 신규 폴더 구조 생성
```bash
mkdir -p backend/app/orchestrator
mkdir -p backend/app/infrastructure/database/repositories
mkdir -p backend/app/infrastructure/config
```

##### 2. 파일 이동 및 분리 (18개 파일 영향)

**orchestrator/** (신규)
- `app/orchestrator/__init__.py` (NEW)
- `app/orchestrator/pipeline.py` ← `app/gateway/service.py` (run_pipeline 부분)
- `app/orchestrator/streaming.py` ← `app/gateway/service.py` (run_pipeline_stream 부분)
- `app/orchestrator/response_builder.py` ← `app/gateway/service.py` (_build_response 부분)

**stages/** (기존 수정)
- `app/stages/registry.py` ← `app/gateway/stage_manager.py` (이동)
- `app/stages/__init__.py` (기존에 이미 존재, import 추가)

**infrastructure/database/** (재구조화)
- `app/infrastructure/database/session.py` ← `app/db/session.py` (이동)
- `app/infrastructure/database/repositories/wiki_repo.py` ← `app/gateway/database/repos/wiki_repo.py`
- `app/infrastructure/database/repositories/rag_repo.py` ← `app/gateway/database/repos/rag_repo.py`
- `app/infrastructure/database/repositories/analysis_repo.py` ← `app/gateway/database/repos/analysis_repo.py`
- `app/infrastructure/database/models/` ← `app/gateway/database/models/` (전체 폴더)

**schemas/** (정리)
- `app/schemas/` ← `app/gateway/schemas/` (common, evidence, verdict 등)
- `app/core/schemas.py` (유지, TruthCheckRequest/Response)

##### 3. Import 업데이트 필요 파일 (약 40개)

**API 레이어 (5개)**
- `app/api/truth_check.py`
- `app/api/rag.py`
- `app/api/wiki.py`
- `app/api/dashboard.py`
- `app/main.py`

**Graph 레이어 (2개)**
- `app/graph/graph.py`
- `app/graph/stage_logger.py`

**Stages (10개)**
- `app/stages/stage01_normalize/node.py`
- `app/stages/stage02_querygen/node.py`
- `app/stages/stage03_collect/node.py`
- `app/stages/stage04_score/node.py`
- `app/stages/stage05_topk/node.py`
- `app/stages/stage06_verify_support/node.py`
- `app/stages/stage07_verify_skeptic/node.py`
- `app/stages/stage08_aggregate/node.py`
- `app/stages/stage09_judge/node.py`
- `app/stages/_shared/*.py`

**Services (6개)**
- `app/services/wiki_usecase.py`
- `app/services/rag_usecase.py`
- `app/services/wiki_retriever.py`
- `app/services/web_rag_service.py`
- `app/services/wiki_query_normalizer.py`
- `app/services/youtube_service.py`

##### 4. 삭제할 폴더/파일
```bash
rm -rf backend/app/gateway/
rm -rf backend/app/db/  # infrastructure로 이동 후
```

#### 단계별 실행 순서

**Step 1: 신규 구조 생성 (30분)**
```bash
# 1. 폴더 생성
mkdir -p backend/app/orchestrator
mkdir -p backend/app/infrastructure/database/repositories
mkdir -p backend/app/infrastructure/config
mkdir -p backend/app/schemas

# 2. __init__.py 생성
touch backend/app/orchestrator/__init__.py
touch backend/app/infrastructure/__init__.py
touch backend/app/infrastructure/database/__init__.py
touch backend/app/infrastructure/database/repositories/__init__.py
touch backend/app/schemas/__init__.py
```

**Step 2: service.py 분할 (2시간)**
```python
# app/orchestrator/response_builder.py (NEW)
from typing import Dict, Any
from app.core.schemas import TruthCheckResponse, Citation

def build_response(state: Dict[str, Any], trace_id: str) -> TruthCheckResponse:
    # _build_response 로직 이동 (60줄)
    pass

# app/orchestrator/pipeline.py (NEW)
from app.orchestrator.response_builder import build_response
from app.graph.graph import run_stage_sequence

def run_pipeline(req: TruthCheckRequest) -> TruthCheckResponse:
    # 기존 run_pipeline 로직
    pass

# app/orchestrator/streaming.py (NEW)
async def run_pipeline_stream(req: TruthCheckRequest):
    # 기존 run_pipeline_stream 로직
    pass
```

**Step 3: DB 레이어 이동 (1시간)**
```bash
# repositories 이동
mv backend/app/gateway/database/repos/*.py backend/app/infrastructure/database/repositories/
mv backend/app/gateway/database/models/ backend/app/infrastructure/database/

# session 이동
cp backend/app/db/session.py backend/app/infrastructure/database/session.py
```

**Step 4: schemas 이동 (30분)**
```bash
mv backend/app/gateway/schemas/*.py backend/app/schemas/
```

**Step 5: Import 일괄 업데이트 (4시간)**
```python
# 찾기/바꾸기 (VSCode Multi-file search)
# Old → New
from app.gateway.service import run_pipeline → from app.orchestrator.pipeline import run_pipeline
from app.gateway.stage_manager import → from app.stages.registry import
from app.db.session import → from app.infrastructure.database.session import
from app.gateway.database.repos import → from app.infrastructure.database.repositories import
from app.gateway.schemas import → from app.schemas import
```

**Step 6: 테스트 및 검증 (2시간)**
```bash
# Import 에러 확인
python -m py_compile backend/app/**/*.py

# 서버 실행 테스트
cd backend && uvicorn app.main:app --reload

# API 호출 테스트
curl http://localhost:8080/health
```

#### 성공 기준
- [ ] 모든 Python 파일이 import 에러 없이 컴파일됨
- [ ] FastAPI 서버가 정상 시작됨
- [ ] `/health`, `/api/truth/check` 엔드포인트가 정상 응답
- [ ] `app/gateway/` 폴더가 존재하지 않음

#### 예상 작업 시간
- 폴더 구조 생성: 30분
- service.py 분할: 2시간
- 파일 이동: 2시간
- Import 업데이트: 4시간
- 테스트: 2시간
- **Total: 10-11시간 (2일)**

---

### P1.2 GraphState Type Safety 강화

#### 목표
TypedDict를 Pydantic BaseModel로 변환하여 런타임 타입 검증 추가

#### 변경 대상 파일 (12개)

##### 1. GraphState 재정의
**파일: `app/graph/state.py`**
```python
# Before
from typing import TypedDict

class GraphState(TypedDict, total=False):
    trace_id: str
    claim_text: str
    # ...

# After
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any

class GraphState(BaseModel):
    """Pipeline state with runtime validation."""
    
    # Required fields
    trace_id: str
    input_type: str
    input_payload: str
    language: str = "ko"
    
    # Optional stage outputs
    claim_text: Optional[str] = None
    canonical_evidence: Optional[Dict[str, Any]] = None
    query_variants: List[Dict[str, Any]] = Field(default_factory=list)
    search_queries: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Evidence chain
    wiki_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    web_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    scored_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Verdicts
    verdict_support: Optional[Dict[str, Any]] = None
    verdict_skeptic: Optional[Dict[str, Any]] = None
    final_verdict: Optional[Dict[str, Any]] = None
    
    # Metadata
    risk_flags: List[str] = Field(default_factory=list)
    stage_logs: List[Dict[str, Any]] = Field(default_factory=list)
    stage_outputs: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(
        extra="allow",  # LangGraph에서 추가 필드 허용
        validate_assignment=True,  # 할당 시 검증
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """LangGraph compatibility."""
        return self.model_dump(exclude_none=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphState":
        """LangGraph compatibility."""
        return cls(**data)
```

##### 2. StageFn 타입 업데이트
**파일: `app/stages/registry.py`**
```python
# Before
from typing import Callable, Dict, Any
StageFn = Callable[[Dict[str, Any]], Dict[str, Any]]

# After
from typing import Callable
from app.graph.state import GraphState

StageFn = Callable[[GraphState], GraphState]
```

##### 3. 모든 Stage 시그니처 통일 (9개 파일)
**변경 패턴:**
```python
# Before
def run(state: dict) -> dict:
    claim = state.get("claim_text", "")
    # ...
    return {"new_field": value}

# After
from app.graph.state import GraphState

def run(state: GraphState) -> GraphState:
    claim = state.claim_text or ""
    # ...
    state.new_field = value
    return state
```

**대상 파일:**
- `app/stages/stage01_normalize/node.py`
- `app/stages/stage02_querygen/node.py`
- `app/stages/stage03_collect/node.py`
- `app/stages/stage04_score/node.py`
- `app/stages/stage05_topk/node.py`
- `app/stages/stage06_verify_support/node.py`
- `app/stages/stage07_verify_skeptic/node.py`
- `app/stages/stage08_aggregate/node.py`
- `app/stages/stage09_judge/node.py`

##### 4. LangGraph Integration 업데이트
**파일: `app/graph/graph.py`**
```python
# Before
def _run_stage(stage_name: str):
    def _runner(state: Dict[str, Any]) -> Dict[str, Any]:
        return run_stage(stage_name, state)
    return _runner

# After
def _run_stage(stage_name: str):
    def _runner(state_dict: Dict[str, Any]) -> Dict[str, Any]:
        # LangGraph는 dict를 주고받으므로 변환 계층 필요
        state = GraphState.from_dict(state_dict)
        result = run_stage(stage_name, state)
        return result.to_dict()
    return _runner
```

##### 5. Mypy 설정 추가
**파일: `backend/pyproject.toml` (또는 `backend/setup.cfg`)**
```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
exclude = [
    "tests/",
    "legacy/",
]

[[tool.mypy.overrides]]
module = [
    "langgraph.*",
    "ddgs.*",
]
ignore_missing_imports = true
```

#### 단계별 실행 순서

**Step 1: GraphState Pydantic 변환 (2시간)**
```bash
# 1. state.py 수정
code backend/app/graph/state.py

# 2. 즉시 테스트
python -c "from app.graph.state import GraphState; s = GraphState(trace_id='test', input_type='text', input_payload='test'); print(s)"
```

**Step 2: Stage 시그니처 일괄 변경 (3시간)**
```python
# 스크립트로 자동화 (검토 후 적용)
import re
import glob

pattern = r"def run\(state: dict\) -> dict:"
replacement = "def run(state: GraphState) -> GraphState:"

for file in glob.glob("backend/app/stages/*/node.py"):
    with open(file, "r") as f:
        content = f.read()
    
    # Import 추가
    if "from app.graph.state import GraphState" not in content:
        content = "from app.graph.state import GraphState\n" + content
    
    # Signature 변경
    content = re.sub(pattern, replacement, content)
    
    # dict.get() → attribute access 변환은 수동 필요
    print(f"Updated: {file}")
```

**Step 3: dict access → attribute access 변환 (4시간)**
```python
# 각 Stage에서 수동 변경 (예시: stage01)
# Before
claim = state.get("claim_text", "")
state["new_field"] = value
return {"claim_text": claim, "language": lang}

# After  
claim = state.claim_text or ""
state.new_field = value
state.claim_text = claim
state.language = lang
return state
```

**Step 4: Mypy 검증 및 타입 에러 수정 (5시간)**
```bash
# Mypy 실행
pip install mypy
mypy backend/app/

# 주요 에러 패턴:
# 1. Optional field 사용 시 None check 누락
if state.claim_text:  # mypy: OK
    process(state.claim_text)

# 2. Any 타입 남용 제거
def process(data: Dict[str, Any]):  # Before
def process(data: Evidence):  # After (proper type)
```

**Step 5: Integration Test (1시간)**
```python
# tests/test_type_safety.py (NEW)
import pytest
from app.graph.state import GraphState
from app.stages.stage01_normalize.node import run as run_stage01

def test_graphstate_validation():
    # Missing required field
    with pytest.raises(ValueError):
        GraphState(trace_id="123")  # Missing input_type, input_payload
    
    # Valid state
    state = GraphState(
        trace_id="123",
        input_type="text",
        input_payload="test claim"
    )
    assert state.trace_id == "123"
    
def test_stage_type_safety():
    state = GraphState(trace_id="123", input_type="text", input_payload="test")
    result = run_stage01(state)
    
    assert isinstance(result, GraphState)
    assert result.claim_text is not None  # Stage01 should set this
```

#### 성공 기준
- [ ] `mypy backend/app/` 실행 시 에러 0개
- [ ] 모든 Stage가 `GraphState → GraphState` 시그니처 사용
- [ ] Pipeline 실행 시 타입 에러 없음
- [ ] 신규 테스트 통과

#### 예상 작업 시간
- GraphState 변환: 2시간
- Stage 시그니처 변경: 3시간
- dict → attribute 변환: 4시간
- Mypy 수정: 5시간
- 테스트: 1시간
- **Total: 15시간 (3일)**

---

### P1.3 에러 처리 통일

#### 목표
일관된 예외 계층, 부분 실패 복구, External API resilience

#### 변경 대상 파일 (15개)

##### 1. Exception Hierarchy 정의
**파일: `app/infrastructure/errors.py` (NEW)**
```python
"""Pipeline exception hierarchy."""
from typing import Optional, Dict, Any

class OLaLaError(Exception):
    """Base exception for all OLaLa errors."""
    pass

class PipelineError(OLaLaError):
    """Base for pipeline execution errors."""
    
    def __init__(
        self,
        message: str,
        stage: str,
        recoverable: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.stage = stage
        self.recoverable = recoverable
        self.context = context or {}
    
    def to_risk_flag(self) -> str:
        return f"{self.stage.upper()}_FAILURE"

class ExternalAPIError(PipelineError):
    """External API call failures (Naver, DDG, Wiki, Ollama)."""
    
    def __init__(self, message: str, stage: str, api_name: str, **kwargs):
        super().__init__(message, stage, recoverable=True, **kwargs)
        self.api_name = api_name

class LLMError(PipelineError):
    """LLM inference errors."""
    
    def __init__(self, message: str, stage: str, model: str, **kwargs):
        super().__init__(message, stage, recoverable=False, **kwargs)
        self.model = model

class ValidationError(PipelineError):
    """Data validation failures."""
    
    def __init__(self, message: str, stage: str, **kwargs):
        super().__init__(message, stage, recoverable=False, **kwargs)
```

##### 2. ErrorHandler 구현
**파일: `app/orchestrator/error_handler.py` (NEW)**
```python
"""Pipeline error recovery handler."""
import logging
from typing import Optional
from app.graph.state import GraphState
from app.infrastructure.errors import PipelineError

logger = logging.getLogger(__name__)

class ErrorHandler:
    """Centralized error handling for pipeline."""
    
    def handle_stage_error(
        self,
        error: Exception,
        state: GraphState,
        stage_name: str,
    ) -> GraphState:
        """
        Handle stage error with recovery policy.
        
        Recoverable errors: Add risk flag, continue
        Fatal errors: Re-raise
        """
        if isinstance(error, PipelineError):
            if error.recoverable:
                logger.warning(
                    f"[{state.trace_id}] Recoverable error in {stage_name}: {error.message}",
                    extra={"context": error.context}
                )
                state.risk_flags.append(error.to_risk_flag())
                return state
            else:
                logger.error(
                    f"[{state.trace_id}] Fatal error in {stage_name}: {error.message}"
                )
                raise error
        else:
            # Unexpected error - wrap and re-raise
            wrapped = PipelineError(
                message=str(error),
                stage=stage_name,
                recoverable=False,
            )
            logger.exception(f"[{state.trace_id}] Unexpected error in {stage_name}")
            raise wrapped from error

error_handler = ErrorHandler()
```

##### 3. External API Wrapper (Retry + Circuit Breaker)
**파일: `app/infrastructure/external_api.py` (NEW)**
```python
"""Resilient external API client."""
import asyncio
import logging
from typing import Optional, Callable, TypeVar, Any
from functools import wraps
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.infrastructure.errors import ExternalAPIError

logger = logging.getLogger(__name__)
T = TypeVar("T")

def with_retry(
    api_name: str,
    stage: str,
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
):
    """Decorator for retrying external API calls."""
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
            reraise=True,
        )
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                    # Server error - retry
                    raise
                elif e.response.status_code == 429:
                    # Rate limit - retry with backoff
                    logger.warning(f"{api_name} rate limited, retrying...")
                    raise
                else:
                    # Client error - don't retry
                    raise ExternalAPIError(
                        message=f"{api_name} client error: {e.response.status_code}",
                        stage=stage,
                        api_name=api_name,
                        context={"status": e.response.status_code},
                    )
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                raise ExternalAPIError(
                    message=f"{api_name} network error: {str(e)}",
                    stage=stage,
                    api_name=api_name,
                )
        
        return wrapper
    return decorator

# Usage example
@with_retry(api_name="Naver", stage="stage03_collect")
async def search_naver(query: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
```

##### 4. Stage 에러 처리 표준화
**변경 파턴 (9개 Stage에 적용):**
```python
# Before
def run(state: dict) -> dict:
    try:
        result = do_something()
    except Exception as e:
        logger.error(f"Error: {e}")
        return state  # Silent failure

# After
from app.infrastructure.errors import PipelineError, ExternalAPIError

def run(state: GraphState) -> GraphState:
    try:
        result = do_something()
    except SomeSpecificError as e:
        raise PipelineError(
            message=f"Failed to process: {str(e)}",
            stage="stage01_normalize",
            recoverable=False,  # or True
            context={"input_length": len(state.input_payload)},
        )
    except Exception as e:
        # Unexpected - wrap and raise
        raise PipelineError(
            message=f"Unexpected error: {str(e)}",
            stage="stage01_normalize",
            recoverable=False,
        ) from e
```

##### 5. Orchestrator에 ErrorHandler 통합
**파일: `app/orchestrator/pipeline.py`**
```python
from app.orchestrator.error_handler import error_handler
from app.infrastructure.errors import PipelineError

def run_pipeline(req: TruthCheckRequest) -> TruthCheckResponse:
    state = GraphState(...)
    
    try:
        result = run_stage_sequence(state, req.start_stage, req.end_stage)
        return build_response(result, state.trace_id)
    except PipelineError as e:
        # Structured error response
        logger.error(f"Pipeline failed: {e.message}", extra={"stage": e.stage})
        return build_error_response(e, state.trace_id)
    except Exception as e:
        logger.exception("Unexpected pipeline failure")
        return build_error_response(
            PipelineError("Internal server error", stage="unknown", recoverable=False),
            state.trace_id
        )
```

#### 단계별 실행 순서

**Step 1: Exception 계층 정의 (1시간)**
```bash
# 1. 파일 생성
touch backend/app/infrastructure/errors.py
touch backend/app/orchestrator/error_handler.py
touch backend/app/infrastructure/external_api.py

# 2. 코드 작성 (위 내용)
```

**Step 2: External API wrapper 구현 (2시간)**
```bash
pip install tenacity httpx

# tests/test_external_api.py 작성하여 retry 로직 검증
```

**Step 3: Stage별 에러 처리 리팩토링 (6시간)**
```python
# 우선순위:
# 1. stage03_collect (External API 많음) - 2시간
# 2. stage01, stage02 (LLM 호출) - 2시간
# 3. 나머지 stages - 2시간
```

**Step 4: Orchestrator 통합 (2시간)**
```python
# pipeline.py, streaming.py에 ErrorHandler 적용
```

**Step 5: E2E 테스트 (2시간)**
```python
# tests/test_error_recovery.py (NEW)
def test_recoverable_error_adds_risk_flag():
    # Simulate Naver API failure
    # Verify pipeline continues with risk flag
    pass

def test_fatal_error_stops_pipeline():
    # Simulate LLM parsing failure
    # Verify pipeline stops and returns error
    pass
```

#### 성공 기준
- [ ] 모든 Stage가 통일된 에러 처리 패턴 사용
- [ ] External API 호출 시 retry 3회 수행
- [ ] Recoverable error 발생 시 risk_flag 추가 후 계속 진행
- [ ] Fatal error 발생 시 구조화된 에러 응답 반환
- [ ] 에러 로그에 stage, context 정보 포함

#### 예상 작업 시간
- Exception 정의: 1시간
- API wrapper: 2시간
- Stage 리팩토링: 6시간
- Orchestrator 통합: 2시간
- 테스트: 2시간
- **Total: 13시간 (2-3일)**

---

## 🟡 Priority 2: High

### P2.1 LangGraph 활용 전략 결정

#### 결정 필요 사항

**옵션 A: LangGraph 고도화** (권장)
- Checkpointing 추가 → 중단/재개 가능
- Conditional routing → Fast/Deep 경로 분기
- Human-in-the-loop → 애매한 판정 시 사람 개입

**옵션 B: 단순화** (Celery 전환)
- LangGraph 제거
- Celery + Redis/RabbitMQ
- 단순 DAG 구조

#### 의사결정 기준
1. **Human-in-the-loop 필요성**: 로드맵에 있는가?
2. **재개 필요성**: Stage 실패 시 처음부터 다시 vs 중단 지점부터?
3. **팀 선호도**: LangGraph vs Celery 경험

#### 권장: 옵션 A (LangGraph 고도화)
이유:
- 이미 LangGraph 인프라 구축됨
- Checkpointing은 MVP 이후 필수기능
- Human-in-the-loop는 진실성 검증의 핵심 차별화 요소

#### 구체적 작업 (옵션 A 선택 시)

##### 1. Checkpointing 추가
**파일: `app/graph/graph.py`**
```python
from langgraph.checkpoint.sqlite import SqliteSaver

# Checkpointer 설정
checkpointer = SqliteSaver.from_conn_string("backend/storage/checkpoints.db")

def build_langgraph() -> Any:
    # ...
    return graph.compile(checkpointer=checkpointer)

# 사용
async def run_pipeline_async(req: TruthCheckRequest) -> TruthCheckResponse:
    state = _init_state(req)
    config = {"configurable": {"thread_id": state.trace_id}}
    
    try:
        result = await app.ainvoke(state, config=config)
    except Exception as e:
        # Checkpoint saved - can resume
        logger.error(f"Pipeline failed, checkpoint saved: {state.trace_id}")
        raise

# 재개 API
@router.post("/api/truth/check/resume/{trace_id}")
async def resume_check(trace_id: str):
    config = {"configurable": {"thread_id": trace_id}}
    # Resume from last successful stage
    result = await app.ainvoke(None, config=config)
    return result
```

##### 2. Conditional Routing (Fast vs Deep Path)
**파일: `app/graph/conditional.py` (NEW)**
```python
from app.graph.state import GraphState

def decide_verification_depth(state: GraphState) -> str:
    """
    Fast path: 단순 사실 확인
    Deep path: 논란있는 주제, 복잡한 검증 필요
    """
    claim = state.claim_text or ""
    
    # Heuristics
    is_simple = (
        len(claim) < 50 and
        state.canonical_evidence.get("confidence", 0) > 0.9
    )
    
    if is_simple:
        return "fast_path"  # Skip Stage06, 07
    else:
        return "deep_path"  # Full verification

# Graph 수정
graph.add_conditional_edges(
    "stage05_topk",
    decide_verification_depth,
    {
        "fast_path": "stage09_judge",  # Direct to judge
        "deep_path": "stage06_verify_support",  # Full verification
    }
)
```

##### 3. Human-in-the-Loop
**파일: `app/graph/interrupt.py` (NEW)**
```python
from langgraph.prebuilt import Interrupt

def stage06_with_human_check(state: GraphState) -> GraphState:
    """Support verification with human review option."""
    result = run_stage06(state)
    
    # If confidence is low, request human review
    if result.verdict_support.get("confidence", 1.0) < 0.5:
        # Interrupt execution
        raise Interrupt(
            value={
                "message": "Low confidence, human review required",
                "verdict": result.verdict_support,
            }
        )
    
    return result

# API for human decision
@router.post("/api/truth/check/{trace_id}/approve")
async def approve_decision(trace_id: str, decision: dict):
    # Resume with human input
    config = {"configurable": {"thread_id": trace_id}}
    # Update state with human decision
    app.update_state(config, {"human_decision": decision})
    # Continue execution
    result = await app.ainvoke(None, config=config)
    return result
```

#### 작업 순서
1. Checkpointing 추가 (1일)
2. Conditional routing 구현 (1일)
3. Human-in-the-loop (2일) - 선택적
4. 테스트 (1일)
- **Total: 5-7일**

---

### P2.2 Stage 동기/비동기 통일

(다음 섹션에 상세 작성 - 공간 절약)

### P2.3 실행 경로 통합

(다음 섹션에 상세 작성 - 공간 절약)

---

## 🟢 Priority 3: Medium

### P3.1 Configuration Management 중앙화

#### 단일 작업 지시서

**파일: `app/infrastructure/config.py` (NEW)**
```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application configuration with validation."""
    
    # Database
    postgres_db: str
    postgres_user: str
    postgres_password: str
    
    @property
    def database_url(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.db_host}:{self.db_port}/{self.postgres_db}"
    
    # LLM
    slm1_base_url: str = "http://ollama:11434/v1"
    slm1_model: str = "exaone3.5:7.8b"
    slm1_max_tokens: int = 2000
    
    slm2_base_url: str = "http://ollama:11434/v1"
    slm2_model: str = "exaone3.5:7.8b"
    
    judge_base_url: str = "http://ollama:11434/v1"
    judge_model: str = "exaone3.5:7.8b"
    
    # External APIs
    naver_client_id: Optional[str] = None
    naver_client_secret: Optional[str] = None
    
    # Features
    wiki_embeddings_ready: bool = False
    allow_online_embed_missing: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Singleton
settings = Settings()
```

**변경 대상 (15개 파일에서 os.getenv 제거):**
```python
# Before
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")

# After
from app.infrastructure.config import settings
OLLAMA_URL = settings.slm1_base_url
```

**예상 시간: 2-3일**

---

## 📋 체크리스트

### P1.1 Gateway 재구조화
- [ ] 신규 폴더 생성 (orchestrator, infrastructure)
- [ ] service.py 3개 파일로 분할
- [ ] DB 레이어 이동 (repositories)
- [ ] schemas 이동
- [ ] Import 일괄 업데이트 (40개 파일)
- [ ] gateway/ 폴더 삭제
- [ ] 서버 시작 테스트
- [ ] API 엔드포인트 동작 확인

### P1.2 Type Safety
- [ ] GraphState Pydantic 변환
- [ ] StageFn 타입 업데이트
- [ ] 9개 Stage 시그니처 변경
- [ ] dict → attribute 변환
- [ ] Mypy 설정 추가
- [ ] Mypy zero errors 달성
- [ ] Type safety 테스트 작성

### P1.3 Error Handling
- [ ] Exception hierarchy 정의
- [ ] ErrorHandler 구현
- [ ] External API wrapper (retry)
- [ ] 9개 Stage 에러 처리 추가
- [ ] Orchestrator 통합
- [ ] Error recovery 테스트

---

## 📅 권장 실행 일정 (2인 팀)

### Week 1
- Mon-Tue: P1.1 Gateway 재구조화
- Wed-Fri: P1.2 Type Safety

### Week 2
- Mon-Tue: P1.3 Error Handling
- Wed-Thu: P3.1 Configuration
- Fri: P2.1 LangGraph 전략 결정

### Week 3-4
- P2.1 LangGraph 구현 (Checkpointing, Conditional)
- P2.2 Async 통일 시작
- P2.3 실행 경로 통합

### Week 5-6
- P2.2 완료
- P3.2 DB 패턴 통일
- P3.3 Observability 추가

---

## 🎯 다음 단계

1. **이 문서 리뷰 및 승인**
2. **우선순위 조정** (필요 시)
3. **Phase 1 착수**: P1.1부터 시작
4. **매주 진행상황 체크**

