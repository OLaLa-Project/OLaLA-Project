"""
Orchestrator runtime utilities for Stage execution.

Minimal runtime to preserve execution flow
(circuit breaker + retry) inside the Stage layer.
"""

import time
import logging
import random
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Set, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OrchestratorError(Exception):
    """Base orchestrator error."""

    def __init__(self, message: str, cause: Optional[Exception] = None):
        super().__init__(message)
        self.cause = cause


class OrchestratorUnavailableError(OrchestratorError):
    """Orchestrator unavailable error (circuit open)."""
    pass


class OrchestratorTimeoutError(OrchestratorError):
    """Orchestrator timeout error."""
    pass


class OrchestratorValidationError(OrchestratorError):
    """Orchestrator validation error."""
    pass


# ---------------------------------------------------------------------------
# Retry Policy
# ---------------------------------------------------------------------------

DEFAULT_RETRYABLE_EXCEPTIONS: Set[Type[Exception]] = {
    ConnectionError,
    TimeoutError,
    OSError,
}


@dataclass
class RetryConfig:
    """Retry policy configuration."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_range: float = 0.5
    retryable_exceptions: Set[Type[Exception]] = field(
        default_factory=lambda: DEFAULT_RETRYABLE_EXCEPTIONS.copy()
    )
    retry_on_status_codes: Set[int] = field(
        default_factory=lambda: {429, 500, 502, 503, 504}
    )


class RetryPolicy:
    """Retry policy implementation."""

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()

    @property
    def max_retries(self) -> int:
        return self.config.max_retries

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        if attempt >= self.config.max_retries:
            logger.debug(f"Max retries ({self.config.max_retries}) exceeded")
            return False

        exception_type = type(exception)
        for retryable_type in self.config.retryable_exceptions:
            if isinstance(exception, retryable_type):
                logger.debug(
                    f"Exception {exception_type.__name__} is retryable, "
                    f"attempt {attempt + 1}/{self.config.max_retries + 1}"
                )
                return True

        status_code = getattr(exception, "status_code", None)
        if status_code is None:
            response = getattr(exception, "response", None)
            if response is not None:
                status_code = getattr(response, "status_code", None)

        if status_code and status_code in self.config.retry_on_status_codes:
            logger.debug(
                f"HTTP status {status_code} is retryable, "
                f"attempt {attempt + 1}/{self.config.max_retries + 1}"
            )
            return True

        logger.debug(f"Exception {exception_type.__name__} is not retryable")
        return False

    def get_delay(self, attempt: int) -> float:
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        delay = min(delay, self.config.max_delay)
        if self.config.jitter:
            jitter_factor = 1 + random.uniform(
                -self.config.jitter_range, self.config.jitter_range
            )
            delay *= jitter_factor
        logger.debug(f"Retry delay for attempt {attempt + 1}: {delay:.2f}s")
        return delay

    def add_retryable_exception(self, exception_type: Type[Exception]) -> None:
        self.config.retryable_exceptions.add(exception_type)

    def add_retryable_status_code(self, status_code: int) -> None:
        self.config.retry_on_status_codes.add(status_code)


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: float = 30.0
    half_open_max_calls: int = 3


@dataclass
class CircuitStats:
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "state_changes": self.state_changes,
            "success_rate": self.success_rate,
        }

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return self.successful_calls / self.total_calls


class CircuitBreaker:
    def __init__(
        self,
        name: str = "default",
        config: Optional[CircuitBreakerConfig] = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0
        self._half_open_calls = 0

        self._stats = CircuitStats()
        self._lock = threading.RLock()

        logger.info(
            f"CircuitBreaker '{name}' initialized: "
            f"failure_threshold={self.config.failure_threshold}, "
            f"timeout={self.config.timeout_seconds}s"
        )

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._check_state_transition()
            return self._state

    @property
    def stats(self) -> CircuitStats:
        return self._stats

    def allow_request(self) -> bool:
        with self._lock:
            self._check_state_transition()
            self._stats.total_calls += 1

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                self._stats.rejected_calls += 1
                logger.debug(f"CircuitBreaker '{self.name}': request rejected (OPEN)")
                return False

            if self._half_open_calls < self.config.half_open_max_calls:
                self._half_open_calls += 1
                logger.debug(
                    f"CircuitBreaker '{self.name}': allowing test request "
                    f"({self._half_open_calls}/{self.config.half_open_max_calls})"
                )
                return True

            self._stats.rejected_calls += 1
            return False

    def record_success(self) -> None:
        with self._lock:
            self._stats.successful_calls += 1
            self._stats.last_success_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.debug(
                    f"CircuitBreaker '{self.name}': success in HALF_OPEN "
                    f"({self._success_count}/{self.config.success_threshold})"
                )

                if self._success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            else:
                self._failure_count = 0

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._stats.failed_calls += 1
            self._last_failure_time = time.time()
            self._stats.last_failure_time = self._last_failure_time

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    f"CircuitBreaker '{self.name}': failure in HALF_OPEN, reopening"
                )
                self._transition_to(CircuitState.OPEN)

            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    logger.warning(
                        f"CircuitBreaker '{self.name}': "
                        f"failure threshold reached ({self._failure_count}), opening"
                    )
                    self._transition_to(CircuitState.OPEN)

    def reset(self) -> None:
        with self._lock:
            logger.info(f"CircuitBreaker '{self.name}': manual reset")
            self._transition_to(CircuitState.CLOSED)

    def _check_state_transition(self) -> None:
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.config.timeout_seconds:
                logger.info(
                    f"CircuitBreaker '{self.name}': "
                    f"timeout elapsed ({elapsed:.1f}s), transitioning to HALF_OPEN"
                )
                self._transition_to(CircuitState.HALF_OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        old_state = self._state
        self._state = new_state
        self._stats.state_changes += 1

        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
            self._half_open_calls = 0
        elif new_state == CircuitState.OPEN:
            self._success_count = 0
            self._half_open_calls = 0

        logger.info(
            f"CircuitBreaker '{self.name}': {old_state.value} -> {new_state.value}"
        )


# ---------------------------------------------------------------------------
# Execute Wrapper
# ---------------------------------------------------------------------------

@dataclass
class OrchestratorRuntime:
    name: str
    circuit_breaker: CircuitBreaker
    retry_policy: RetryPolicy

    def execute(
        self,
        operation: Callable[[], T],
        operation_name: str,
        skip_circuit_breaker: bool = False,
        skip_retry: bool = False,
    ) -> T:
        if not skip_circuit_breaker and not self.circuit_breaker.allow_request():
            raise OrchestratorUnavailableError(
                f"Orchestrator '{self.name}' circuit is open for '{operation_name}'"
            )

        start_time = time.time()
        last_error: Optional[Exception] = None
        max_attempts = 1 if skip_retry else (self.retry_policy.max_retries + 1)

        for attempt in range(max_attempts):
            try:
                result = operation()
                if not skip_circuit_breaker:
                    self.circuit_breaker.record_success()
                return result

            except Exception as e:
                last_error = e
                if skip_retry or not self.retry_policy.should_retry(e, attempt):
                    break

                delay = self.retry_policy.get_delay(attempt)
                logger.info(
                    f"{operation_name} retrying in {delay:.2f}s "
                    f"(attempt {attempt + 2}/{max_attempts})"
                )
                time.sleep(delay)

        error_msg = str(last_error) if last_error else "Unknown error"
        if not skip_circuit_breaker:
            self.circuit_breaker.record_failure()

        raise OrchestratorError(
            f"Orchestrator '{self.name}' operation '{operation_name}' failed: {error_msg}",
            cause=last_error,
        )
