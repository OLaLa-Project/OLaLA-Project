"""
OLaLA Gateway Layer

통합 Gateway 아키텍처:
- 스키마 표준화 및 검증
- Circuit Breaker 패턴
- 재시도 정책
- 메트릭 수집

Components:
- core: 공통 인프라 (CircuitBreaker, RetryPolicy, Metrics)
- schemas: 통합 스키마 정의
- llm: LLM/SLM 호출 관리
- embedding: 임베딩 서비스 관리
- database: 데이터베이스 작업 관리
- external: 외부 API 관리 (Naver, Docker)
"""

from .core.base_gateway import BaseGateway, GatewayError, GatewayUnavailableError
from .core.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerConfig
from .core.retry_policy import RetryPolicy, RetryConfig
from .core.metrics import MetricsCollector, GatewayMetrics

__all__ = [
    "BaseGateway",
    "GatewayError",
    "GatewayUnavailableError",
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerConfig",
    "RetryPolicy",
    "RetryConfig",
    "MetricsCollector",
    "GatewayMetrics",
]
