# OLaLA 리팩토링 우선순위 및 영향도 분석

**작성일:** 2026-02-06
**작성자:** Senior Full-Stack & MLOps Tech Lead
**대상:** OLaLA-Project-sub_gateway 2

---

## 개요

본 문서는 OLaLA 백엔드 프로젝트의 리팩토링 우선순위를 정의하고, 각 항목별 영향도와 기대효과, 리스크를 분석합니다.

---

## Top-K 리팩토링 우선순위

| 순위 | 항목 | 예상 일수 | 긴급도 |
|:----:|------|:---------:|:------:|
| #1 | 테스트 프레임워크 구축 | 3-4일 | Critical |
| #2 | Type Safety 강화 | 3-4일 | Critical |
| #3 | API 에러 처리 추가 | 1일 | High |
| #4 | Config 중앙화 | 2일 | High |
| #5 | 실행 경로 통합 | 1-2일 | Medium |
| #6 | LangGraph Checkpointing | 2-3일 | Medium |
| #7 | External API Rate Limiting | 2일 | Medium |
| #8 | Observability (로깅/메트릭) | 3-4일 | Medium |
| #9 | Stage Async 통일 | 5-7일 | Low |
| #10 | Gateway 리네이밍 | 1-2일 | Low |

---

## #1 테스트 프레임워크 구축

### 영향도

| 영향 범위 | 파일 수 | 설명 |
|----------|--------|------|
| 신규 생성 | 10-15개 | tests/ 하위 구조, conftest.py, CI 설정 |
| 기존 수정 | 0개 | 기존 코드 수정 없음 |
| 의존성 추가 | 3-4개 | pytest, pytest-asyncio, pytest-cov, httpx |

### 긍정적 효과

| 항목 | 효과 |
|------|------|
| **안전망 확보** | 이후 모든 리팩토링 시 회귀버그 즉시 탐지 |
| **개발 속도 향상** | "고쳤는데 다른 데서 터짐" 방지 |
| **코드 품질 가시화** | 커버리지 리포트로 취약 지점 파악 |
| **CI 자동화** | PR마다 자동 테스트, 리뷰 부담 감소 |
| **문서화 효과** | 테스트 코드가 사용법 예시 역할 |

### 부정적 효과 및 리스크

| 항목 | 리스크 | 완화 방안 |
|------|--------|----------|
| **초기 시간 투자** | 3-4일 소요, 당장 기능 추가 없음 | 핵심 Stage만 먼저 (1, 2, 3) |
| **테스트 유지 비용** | 코드 변경 시 테스트도 수정 필요 | 과도한 mock 지양, 통합 테스트 위주 |
| **외부 의존성 Mocking** | Ollama, Naver API mock 복잡 | fixtures로 표준화 |

### 결론

```
리스크 < 이점 (압도적)
권장: 무조건 먼저 진행
```

---

## #2 Type Safety 강화

### 영향도

| 영향 범위 | 파일 수 | 설명 |
|----------|--------|------|
| Stage 파일 | 9개 | 모든 stage의 run() 시그니처 변경 |
| graph.py | 1개 | _run_stage, wrapper 함수 타입 수정 |
| service.py | 1개 | State 초기화 타입 변경 |
| state.py | 1개 | GraphState 검증 로직 추가 가능 |

### 긍정적 효과

| 항목 | 효과 |
|------|------|
| **컴파일 타임 오류 탐지** | `state.get("cliam_text")` 오타 → IDE에서 즉시 발견 |
| **IDE 자동완성** | 50+ 필드를 외울 필요 없음 |
| **Stage 간 계약 명확화** | 어떤 Stage가 어떤 필드 사용하는지 추적 가능 |
| **리팩토링 안전성** | 필드명 변경 시 영향 범위 자동 파악 |
| **신규 개발자 온보딩** | 코드만 봐도 데이터 흐름 이해 |

### 부정적 효과 및 리스크

| 항목 | 리스크 | 완화 방안 |
|------|--------|----------|
| **대량 수정** | 9개 Stage + 2개 핵심 파일 | 한 Stage씩 점진적 적용 |
| **Mypy 에러 폭발** | 처음 적용 시 100+ 에러 예상 | strict mode 단계적 적용 |
| **TypedDict 한계** | 런타임 검증 없음 | Pydantic TypeAdapter 추가 검토 |
| **동적 필드 문제** | `state[dynamic_key]` 패턴 불가 | total=False로 유연성 유지 |

### 결론

```
단기 고통, 장기 이익
권장: #1 테스트 후 바로 진행
```

---

## #3 API 에러 처리 추가

### 영향도

| 영향 범위 | 파일 수 | 설명 |
|----------|--------|------|
| truth_check.py | 1개 | try-except 추가 |
| 신규 생성 | 1개 | errors.py (커스텀 예외 정의) |
| main.py | 1개 | 전역 exception handler 추가 가능 |

### 긍정적 효과

| 항목 | 효과 |
|------|------|
| **사용자 경험 개선** | 500 에러 → 친절한 에러 메시지 |
| **디버깅 용이** | 에러 로깅으로 원인 추적 가능 |
| **서비스 안정성** | 한 요청 실패가 서버 크래시 안 함 |
| **모니터링 기반** | 에러 패턴 분석 가능 |

### 부정적 효과 및 리스크

| 항목 | 리스크 | 완화 방안 |
|------|--------|----------|
| **에러 삼키기** | 잘못된 catch로 버그 숨김 | 로깅 필수, 구체적 예외 타입 |
| **중복 처리** | service.py에도 try-except 있음 | 레이어별 역할 명확히 |

### 변경 예시

```python
# 현재 (위험)
@router.post("/truth/check")
def truth_check(req: TruthCheckRequest, db: Session = Depends(get_db)):
    result = run_pipeline(req)  # 예외 발생 시 500 에러
    return result

# 수정 후
@router.post("/truth/check")
def truth_check(req: TruthCheckRequest, db: Session = Depends(get_db)):
    try:
        result = run_pipeline(req)
        AnalysisRepository(db).save_analysis(result.model_dump())
        return result
    except Exception as e:
        logger.exception("Pipeline failed")
        raise HTTPException(status_code=500, detail="분석 중 오류 발생")
```

### 결론

```
리스크 매우 낮음, 효과 높음
권장: 1일이면 충분, 즉시 진행
```

---

## #4 Config 중앙화

### 영향도

| 영향 범위 | 파일 수 | 설명 |
|----------|--------|------|
| 신규 생성 | 1개 | config.py (Settings 클래스) |
| 수정 필요 | 5-7개 | os.getenv 사용하는 모든 파일 |
| 의존성 추가 | 1개 | pydantic-settings |

### 긍정적 효과

| 항목 | 효과 |
|------|------|
| **시작 시 검증** | 필수 환경변수 누락 → 앱 시작 실패 (빠른 실패) |
| **타입 안전성** | `str` → `int`, `bool` 자동 변환 |
| **기본값 중앙 관리** | 중복 기본값 불일치 방지 |
| **문서화 효과** | Settings 클래스가 필요한 환경변수 목록 |
| **테스트 용이** | Settings 객체 mock으로 테스트 환경 분리 |

### 부정적 효과 및 리스크

| 항목 | 리스크 | 완화 방안 |
|------|--------|----------|
| **마이그레이션 작업** | 기존 os.getenv 모두 교체 필요 | 점진적 적용 (신규 먼저) |
| **순환 import 위험** | config.py를 여러 곳에서 import | 최상위 모듈로 분리 |
| **.env 파일 관리** | 로컬/개발/프로덕션 분리 필요 | .env.example 템플릿 제공 |

### 변경 예시

```python
# 현재 (분산)
# slm_client.py: os.getenv("SLM1_BASE_URL")
# stage03: os.getenv("NAVER_CLIENT_ID")
# graph.py: os.getenv("WIKI_EMBEDDINGS_READY")

# 수정 후
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    slm1_base_url: str
    naver_client_id: str
    wiki_embeddings_ready: bool = False

    class Config:
        env_file = ".env"

settings = Settings()  # 시작 시 누락된 환경변수 즉시 발견
```

### 결론

```
운영 안정성 대폭 향상
권장: 2일 투자 가치 충분
```

---

## #5 실행 경로 통합

### 영향도

| 영향 범위 | 파일 수 | 설명 |
|----------|--------|------|
| service.py | 1개 | _init_state() 함수 추출, 두 함수에서 호출 |

### 긍정적 효과

| 항목 | 효과 |
|------|------|
| **DRY 원칙** | 11줄 중복 제거 |
| **버그 수정 한 곳만** | State 필드 추가/수정 시 실수 방지 |
| **테스트 용이** | _init_state() 단독 테스트 가능 |
| **코드 가독성** | 의도 명확 (초기화 vs 실행) |

### 부정적 효과 및 리스크

| 항목 | 리스크 | 완화 방안 |
|------|--------|----------|
| **리스크 거의 없음** | 단순 추출 리팩토링 | 테스트로 동작 확인 |

### 변경 예시

```python
# 현재 (중복)
def run_pipeline(...):
    state: Dict[str, Any] = {"trace_id": ..., "input_type": ...}  # 중복 1

async def run_pipeline_stream(...):
    state: Dict[str, Any] = {"trace_id": ..., "input_type": ...}  # 중복 2

# 수정 후
def _init_state(req: TruthCheckRequest) -> GraphState:
    return {"trace_id": str(uuid.uuid4()), ...}  # 한 곳에서만

def run_pipeline(req):
    state = _init_state(req)
    ...

async def run_pipeline_stream(req):
    state = _init_state(req)
    ...
```

### 결론

```
가장 안전한 리팩토링
권장: 1-2시간이면 충분
```

---

## #6 LangGraph Checkpointing 추가

### 영향도

| 영향 범위 | 파일 수 | 설명 |
|----------|--------|------|
| graph.py | 1개 | graph.compile(checkpointer=...) |
| 신규 생성 | 1개 | checkpoints 테이블 또는 SQLite 파일 |
| service.py | 1개 | thread_id 전달 로직 추가 |

### 긍정적 효과

| 항목 | 효과 |
|------|------|
| **중간 재개 가능** | Stage 5에서 실패 → Stage 5부터 재시작 |
| **비용 절감** | LLM 호출 중복 방지 |
| **디버깅 강화** | 중간 상태 스냅샷으로 문제 분석 |
| **사용자 경험** | 긴 파이프라인 중단 시 처음부터 안 해도 됨 |

### 부정적 효과 및 리스크

| 항목 | 리스크 | 완화 방안 |
|------|--------|----------|
| **저장소 필요** | SQLite 또는 PostgreSQL 테이블 | SQLite로 시작 (간단) |
| **상태 직렬화** | 복잡한 객체 직렬화 문제 가능 | Dict 기반이라 대부분 OK |
| **만료 정책 필요** | 오래된 체크포인트 정리 | TTL 설정 |

### 결론

```
LangGraph 제대로 활용하는 첫 걸음
권장: Top 1-5 후 진행
```

---

## #7 External API Rate Limiting

### 영향도

| 영향 범위 | 파일 수 | 설명 |
|----------|--------|------|
| stage03_collect/node.py | 1개 | aiolimiter 또는 semaphore 추가 |
| 의존성 추가 | 1-2개 | aiolimiter, tenacity |

### 긍정적 효과

| 항목 | 효과 |
|------|------|
| **API 차단 방지** | Naver/DDG quota 초과 방지 |
| **안정적 서비스** | 429 에러 자동 재시도 |
| **비용 예측** | API 호출량 제어 가능 |

### 부정적 효과 및 리스크

| 항목 | 리스크 | 완화 방안 |
|------|--------|----------|
| **응답 시간 증가** | Rate limit 대기 시간 | 합리적 limit 설정 (초당 5회 등) |
| **복잡도 증가** | 비동기 제어 로직 추가 | 잘 검증된 라이브러리 사용 |

### 결론

```
프로덕션 필수, 개발 환경에선 선택
권장: 프로덕션 배포 전 필수
```

---

## #8 Observability (로깅/메트릭)

### 영향도

| 영향 범위 | 파일 수 | 설명 |
|----------|--------|------|
| 신규 생성 | 2-3개 | metrics.py, tracing.py |
| Stage 파일 | 9개 | 메트릭 수집 코드 추가 |
| main.py | 1개 | Prometheus endpoint 추가 |
| 인프라 | - | Prometheus + Grafana 설정 |

### 긍정적 효과

| 항목 | 효과 |
|------|------|
| **성능 가시화** | Stage별 P50/P95 latency 확인 |
| **장애 조기 탐지** | 에러율 급증 알림 |
| **용량 계획** | LLM 토큰 사용량 추적 |
| **SLA 관리** | 응답 시간 목표 모니터링 |

### 부정적 효과 및 리스크

| 항목 | 리스크 | 완화 방안 |
|------|--------|----------|
| **인프라 복잡도** | Prometheus/Grafana 운영 필요 | 클라우드 매니지드 서비스 사용 |
| **코드 침투** | 모든 Stage에 메트릭 코드 | 데코레이터 패턴으로 최소화 |
| **오버헤드** | 메트릭 수집 비용 | 샘플링으로 최적화 |

### 결론

```
프로덕션 운영 필수
권장: 기본 메트릭부터 시작, 점진적 확장
```

---

## #9 Stage Async 통일

### 영향도

| 영향 범위 | 파일 수 | 설명 |
|----------|--------|------|
| Stage 파일 | 6-7개 | sync → async 전환 |
| slm_client.py | 1개 | requests → httpx async |
| DB 관련 | 2-3개 | SQLAlchemy async 또는 asyncpg |
| graph.py | 1개 | wrapper 제거/단순화 |

### 긍정적 효과

| 항목 | 효과 |
|------|------|
| **진정한 병렬성** | I/O 대기 중 다른 작업 가능 |
| **이벤트 루프 충돌 해소** | asyncio.run() 문제 제거 |
| **코드 일관성** | 모든 Stage 동일 패턴 |
| **성능 향상** | 동시 요청 처리량 증가 |

### 부정적 효과 및 리스크

| 항목 | 리스크 | 완화 방안 |
|------|--------|----------|
| **대규모 변경** | 6-7개 파일 전면 수정 | 한 Stage씩 점진적 |
| **DB 마이그레이션** | SQLAlchemy async 전환 복잡 | asyncpg 직접 사용 또는 유지 |
| **테스트 수정** | async 테스트 패턴 필요 | pytest-asyncio 활용 |
| **학습 곡선** | async/await 패턴 숙지 필요 | 팀 역량에 따라 판단 |

### 결론

```
효과 크지만 비용도 큼
권장: 안정화 후 진행 (Phase 3)
```

---

## #10 Gateway 리네이밍

### 영향도

| 영향 범위 | 파일 수 | 설명 |
|----------|--------|------|
| 디렉토리 이동 | 3-4개 | gateway/ → orchestrator/ |
| import 수정 | 10-15개 | from app.gateway → from app.orchestrator |

### 긍정적 효과

| 항목 | 효과 |
|------|------|
| **아키텍처 의도 명확** | 이름이 역할을 설명 |
| **신규 개발자 온보딩** | "Gateway가 왜 2개?" 혼란 제거 |
| **책임 분리 촉진** | 이름에 맞게 코드 정리 유도 |

### 부정적 효과 및 리스크

| 항목 | 리스크 | 완화 방안 |
|------|--------|----------|
| **import 수정** | 10-15개 파일 수정 | IDE 리팩토링 기능 활용 |
| **Git 히스토리** | 파일 이동으로 blame 추적 어려움 | git mv 사용 |
| **실제 동작 변화 없음** | 이름만 바꾸는 작업 | 다른 작업과 함께 진행 |

### 결론

```
효과 대비 비용 낮음
권장: 다른 작업 중 자연스럽게 진행
```

---

## 종합 ROI 분석

| 순위 | 항목 | 긍정 | 부정 | ROI |
|:----:|------|:----:|:----:|:---:|
| #1 | 테스트 구축 | +++++ | + | **최상** |
| #2 | Type Safety | ++++ | ++ | **상** |
| #3 | API 에러 처리 | +++ | + | **상** |
| #4 | Config 중앙화 | +++ | + | **상** |
| #5 | 실행 경로 통합 | ++ | - | **상** |
| #6 | Checkpointing | +++ | ++ | 중 |
| #7 | Rate Limiting | +++ | + | 중 |
| #8 | Observability | ++++ | +++ | 중 |
| #9 | Async 통일 | ++++ | ++++ | **낮음** |
| #10 | Gateway 리네이밍 | ++ | + | 중 |

---

## 실행 로드맵

### Phase 1: 안전망 구축 (Week 1)

```
Day 1-2: #1 테스트 프레임워크 기본 설정
Day 3:   #3 API 에러 처리 추가
Day 4-5: #1 핵심 Stage 테스트 작성 (Stage 1, 2, 3)
```

### Phase 2: 안정성 강화 (Week 2)

```
Day 1-3: #2 Type Safety 강화
Day 4:   #4 Config 중앙화
Day 5:   #5 실행 경로 통합
```

### Phase 3: 고급 기능 (Week 3-4)

```
Day 1-2: #6 LangGraph Checkpointing
Day 3-4: #7 Rate Limiting
Day 5-8: #8 Observability
```

### Phase 4: 최적화 (Week 5-6)

```
Day 1-5: #9 Stage Async 통일
Day 6-7: #10 Gateway 리네이밍
```

---

## Quick Wins (즉시 적용 가능)

### 1. Mypy 설정 추가 (1시간)

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
disallow_untyped_defs = true
```

### 2. Pre-commit hooks (1시간)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks:
      - id: mypy
```

### 3. ENV validation (2시간)

```python
# app/core/startup.py
required = ["SLM1_BASE_URL", "POSTGRES_DB", "NAVER_CLIENT_ID"]
missing = [k for k in required if not os.getenv(k)]
if missing:
    raise RuntimeError(f"Missing env vars: {missing}")
```

---

## 핵심 원칙

```
#1 테스트 → 나머지 모든 작업의 안전망
#2 Type Safety → 버그 예방의 근본
#3-5 → 빠르게 끝나는 고효율 작업

"테스트 먼저, 타입 다음, 나머지는 순서대로"
```

---

*문서 끝*
