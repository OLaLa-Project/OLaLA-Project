"""
Base Gateway Implementation.

모든 Gateway의 기본 클래스입니다.

Features:
- 통합 실행 래퍼 (Circuit Breaker + Retry + Metrics)
- 스키마 검증
- 에러 처리
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Callable, Optional, Any
from functools import wraps

from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .retry_policy import RetryPolicy, RetryConfig
from .metrics import MetricsCollector, get_global_metrics

logger = logging.getLogger(__name__)

T = TypeVar("T")


class GatewayError(Exception):
    """Gateway 기본 에러."""

    def __init__(self, message: str, cause: Optional[Exception] = None):
        super().__init__(message)
        self.cause = cause


class GatewayUnavailableError(GatewayError):
    """Gateway 사용 불가 에러 (Circuit Open)."""
    pass


class GatewayTimeoutError(GatewayError):
    """Gateway 타임아웃 에러."""
    pass


class GatewayValidationError(GatewayError):
    """Gateway 스키마 검증 에러."""
    pass


class BaseGateway(ABC):
    """
    모든 Gateway의 기본 클래스.

    제공 기능:
    - Circuit Breaker 패턴
    - 재시도 정책
    - 메트릭 수집
    - 통합 실행 래퍼

    사용 예:
        class LLMGateway(BaseGateway):
            def __init__(self):
                super().__init__(
                    name="llm",
                    circuit_config=CircuitBreakerConfig(failure_threshold=3),
                    retry_config=RetryConfig(max_retries=2),
                )

            def generate(self, prompt: str) -> str:
                def operation():
                    return self._call_llm(prompt)

                return self.execute(operation, "generate")
    """

    def __init__(
        self,
        name: str,
        circuit_config: Optional[CircuitBreakerConfig] = None,
        retry_config: Optional[RetryConfig] = None,
        metrics: Optional[MetricsCollector] = None,
    ):
        """
        Args:
            name: Gateway 이름 (메트릭/로깅에 사용)
            circuit_config: Circuit Breaker 설정
            retry_config: 재시도 정책 설정
            metrics: 메트릭 수집기 (None이면 전역 사용)
        """
        self.name = name
        self.circuit_breaker = CircuitBreaker(
            name=name,
            config=circuit_config or CircuitBreakerConfig(),
        )
        self.retry_policy = RetryPolicy(
            config=retry_config or RetryConfig(),
        )
        self.metrics = metrics or get_global_metrics()
        self.logger = logging.getLogger(f"gateway.{name}")

        self.logger.info(f"Gateway '{name}' initialized")

    def execute(
        self,
        operation: Callable[[], T],
        operation_name: str,
        skip_circuit_breaker: bool = False,
        skip_retry: bool = False,
    ) -> T:
        """
        통합 실행 래퍼.

        Circuit Breaker, 재시도, 메트릭 수집을 적용합니다.

        Args:
            operation: 실행할 작업 (람다 또는 함수)
            operation_name: 작업 이름 (메트릭/로깅용)
            skip_circuit_breaker: Circuit Breaker 건너뛰기
            skip_retry: 재시도 건너뛰기

        Returns:
            작업 결과

        Raises:
            GatewayUnavailableError: Circuit이 열려있는 경우
            GatewayError: 모든 재시도 실패
        """
        # Circuit Breaker 체크
        if not skip_circuit_breaker and not self.circuit_breaker.allow_request():
            self.metrics.record_circuit_open(self.name, operation_name)
            raise GatewayUnavailableError(
                f"Gateway '{self.name}' circuit is open for '{operation_name}'"
            )

        start_time = time.time()
        last_error: Optional[Exception] = None
        max_attempts = 1 if skip_retry else (self.retry_policy.max_retries + 1)

        for attempt in range(max_attempts):
            try:
                result = operation()

                # 성공 기록
                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record_success(self.name, operation_name, latency_ms)

                if not skip_circuit_breaker:
                    self.circuit_breaker.record_success()

                self.logger.debug(
                    f"{operation_name} succeeded in {latency_ms:.2f}ms "
                    f"(attempt {attempt + 1})"
                )

                return result

            except Exception as e:
                last_error = e
                latency_ms = (time.time() - start_time) * 1000

                self.logger.warning(
                    f"{operation_name} failed (attempt {attempt + 1}): {e}"
                )

                # 재시도 가능 여부 확인
                if skip_retry or not self.retry_policy.should_retry(e, attempt):
                    break

                # 재시도 대기
                delay = self.retry_policy.get_delay(attempt)
                self.logger.info(
                    f"{operation_name} retrying in {delay:.2f}s "
                    f"(attempt {attempt + 2}/{max_attempts})"
                )
                time.sleep(delay)

        # 최종 실패
        latency_ms = (time.time() - start_time) * 1000
        error_msg = str(last_error) if last_error else "Unknown error"

        self.metrics.record_failure(
            self.name, operation_name, latency_ms, error_msg
        )

        if not skip_circuit_breaker:
            self.circuit_breaker.record_failure()

        raise GatewayError(
            f"Gateway '{self.name}' operation '{operation_name}' failed: {error_msg}",
            cause=last_error,
        )

    def execute_async(
        self,
        operation: Callable[[], T],
        operation_name: str,
    ) -> T:
        """
        비동기 실행 래퍼 (async 함수용).

        TODO: asyncio 지원 추가
        """
        raise NotImplementedError("Async execution not yet implemented")

    def get_status(self) -> dict:
        """Gateway 상태 조회."""
        return {
            "name": self.name,
            "circuit_breaker": self.circuit_breaker.get_status(),
            "metrics": self.metrics.get_metrics(self.name),
        }

    def reset_circuit_breaker(self) -> None:
        """Circuit Breaker 수동 리셋."""
        self.circuit_breaker.reset()
        self.logger.info(f"Circuit breaker reset for '{self.name}'")

    def reset_metrics(self) -> None:
        """메트릭 리셋."""
        self.metrics.reset(self.name)
        self.logger.info(f"Metrics reset for '{self.name}'")


def gateway_operation(operation_name: str):
    """
    Gateway 작업 데코레이터.

    BaseGateway를 상속한 클래스의 메서드에 사용합니다.

    사용 예:
        class LLMGateway(BaseGateway):
            @gateway_operation("generate")
            def generate(self, prompt: str) -> str:
                return self._call_llm(prompt)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(self: BaseGateway, *args, **kwargs) -> T:
            def operation():
                return func(self, *args, **kwargs)

            return self.execute(operation, operation_name)

        return wrapper

    return decorator
