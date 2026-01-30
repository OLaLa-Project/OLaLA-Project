"""
Circuit Breaker Pattern Implementation.

연속 실패 시 서비스 호출을 차단하여 연쇄 장애를 방지합니다.

States:
- CLOSED: 정상 작동, 모든 요청 허용
- OPEN: 차단됨, 모든 요청 거부 (timeout 후 HALF_OPEN으로 전환)
- HALF_OPEN: 테스트 중, 제한된 요청 허용 (성공 시 CLOSED, 실패 시 OPEN)
"""

import time
import threading
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit Breaker 상태."""
    CLOSED = "closed"       # 정상 작동
    OPEN = "open"           # 차단됨
    HALF_OPEN = "half_open" # 테스트 중


@dataclass
class CircuitBreakerConfig:
    """Circuit Breaker 설정."""

    failure_threshold: int = 5
    """연속 실패 횟수 임계값 (이 값 이상 실패 시 OPEN)"""

    success_threshold: int = 2
    """HALF_OPEN 상태에서 연속 성공 횟수 (이 값 이상 성공 시 CLOSED)"""

    timeout_seconds: float = 30.0
    """OPEN 상태 유지 시간 (이후 HALF_OPEN으로 전환)"""

    half_open_max_calls: int = 3
    """HALF_OPEN 상태에서 허용할 최대 동시 요청 수"""


@dataclass
class CircuitStats:
    """Circuit Breaker 통계."""

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
    """
    Circuit Breaker 패턴 구현.

    사용 예:
        cb = CircuitBreaker(name="ollama")

        if cb.allow_request():
            try:
                result = call_external_service()
                cb.record_success()
                return result
            except Exception as e:
                cb.record_failure()
                raise
        else:
            raise CircuitOpenError("Service unavailable")
    """

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
        """현재 상태 반환."""
        with self._lock:
            self._check_state_transition()
            return self._state

    @property
    def stats(self) -> CircuitStats:
        """통계 반환."""
        return self._stats

    def allow_request(self) -> bool:
        """
        요청 허용 여부 확인.

        Returns:
            True: 요청 허용
            False: 요청 거부 (Circuit OPEN)
        """
        with self._lock:
            self._check_state_transition()
            self._stats.total_calls += 1

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                self._stats.rejected_calls += 1
                logger.debug(f"CircuitBreaker '{self.name}': request rejected (OPEN)")
                return False

            # HALF_OPEN: 제한된 요청 허용
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
        """성공 기록."""
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
                # CLOSED 상태에서는 실패 카운터 리셋
                self._failure_count = 0

    def record_failure(self) -> None:
        """실패 기록."""
        with self._lock:
            self._failure_count += 1
            self._stats.failed_calls += 1
            self._last_failure_time = time.time()
            self._stats.last_failure_time = self._last_failure_time

            if self._state == CircuitState.HALF_OPEN:
                # HALF_OPEN에서 실패 → 즉시 OPEN
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
        """수동 리셋 (CLOSED 상태로)."""
        with self._lock:
            logger.info(f"CircuitBreaker '{self.name}': manual reset")
            self._transition_to(CircuitState.CLOSED)

    def force_open(self) -> None:
        """수동으로 OPEN 상태로 전환."""
        with self._lock:
            logger.warning(f"CircuitBreaker '{self.name}': forced open")
            self._transition_to(CircuitState.OPEN)

    def _check_state_transition(self) -> None:
        """상태 전환 확인 (OPEN → HALF_OPEN)."""
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.config.timeout_seconds:
                logger.info(
                    f"CircuitBreaker '{self.name}': "
                    f"timeout elapsed ({elapsed:.1f}s), transitioning to HALF_OPEN"
                )
                self._transition_to(CircuitState.HALF_OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        """상태 전환."""
        old_state = self._state
        self._state = new_state
        self._stats.state_changes += 1

        # 상태별 카운터 리셋
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
            f"CircuitBreaker '{self.name}': {old_state.value} → {new_state.value}"
        )

    def get_status(self) -> dict:
        """현재 상태 정보 반환."""
        with self._lock:
            self._check_state_transition()
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "success_threshold": self.config.success_threshold,
                    "timeout_seconds": self.config.timeout_seconds,
                },
                "stats": self._stats.to_dict(),
            }
