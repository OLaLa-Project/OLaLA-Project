"""
Retry Policy Implementation.

지수 백오프와 지터를 적용한 재시도 정책입니다.

Features:
- Exponential backoff with jitter
- Configurable retry conditions
- Per-exception-type retry rules
"""

import random
import time
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional, Set, Type
from functools import wraps

logger = logging.getLogger(__name__)


# 기본적으로 재시도 가능한 예외들
DEFAULT_RETRYABLE_EXCEPTIONS: Set[Type[Exception]] = {
    ConnectionError,
    TimeoutError,
    OSError,
}


@dataclass
class RetryConfig:
    """재시도 정책 설정."""

    max_retries: int = 3
    """최대 재시도 횟수"""

    base_delay: float = 1.0
    """기본 대기 시간 (초)"""

    max_delay: float = 30.0
    """최대 대기 시간 (초)"""

    exponential_base: float = 2.0
    """지수 백오프 밑수"""

    jitter: bool = True
    """지터(무작위성) 적용 여부"""

    jitter_range: float = 0.5
    """지터 범위 (0.5 = ±50%)"""

    retryable_exceptions: Set[Type[Exception]] = field(
        default_factory=lambda: DEFAULT_RETRYABLE_EXCEPTIONS.copy()
    )
    """재시도 가능한 예외 타입들"""

    retry_on_status_codes: Set[int] = field(
        default_factory=lambda: {429, 500, 502, 503, 504}
    )
    """재시도할 HTTP 상태 코드들"""


class RetryPolicy:
    """
    재시도 정책 구현.

    사용 예:
        policy = RetryPolicy()

        for attempt in range(policy.max_retries + 1):
            try:
                result = call_service()
                return result
            except Exception as e:
                if not policy.should_retry(e, attempt):
                    raise
                time.sleep(policy.get_delay(attempt))
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()

    @property
    def max_retries(self) -> int:
        return self.config.max_retries

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """
        재시도 여부 결정.

        Args:
            exception: 발생한 예외
            attempt: 현재 시도 횟수 (0-indexed)

        Returns:
            True: 재시도 해야 함
            False: 재시도 하지 않음
        """
        # 최대 재시도 횟수 초과
        if attempt >= self.config.max_retries:
            logger.debug(f"Max retries ({self.config.max_retries}) exceeded")
            return False

        # 예외 타입 확인
        exception_type = type(exception)
        for retryable_type in self.config.retryable_exceptions:
            if isinstance(exception, retryable_type):
                logger.debug(
                    f"Exception {exception_type.__name__} is retryable, "
                    f"attempt {attempt + 1}/{self.config.max_retries + 1}"
                )
                return True

        # HTTP 상태 코드 확인 (requests.HTTPError 등)
        status_code = getattr(exception, "status_code", None)
        if status_code is None:
            # response 속성에서 확인
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
        """
        재시도 전 대기 시간 계산.

        Args:
            attempt: 현재 시도 횟수 (0-indexed)

        Returns:
            대기 시간 (초)
        """
        # 지수 백오프: base_delay * (exponential_base ^ attempt)
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)

        # 최대 대기 시간 제한
        delay = min(delay, self.config.max_delay)

        # 지터 적용
        if self.config.jitter:
            jitter_factor = 1 + random.uniform(
                -self.config.jitter_range, self.config.jitter_range
            )
            delay *= jitter_factor

        logger.debug(f"Retry delay for attempt {attempt + 1}: {delay:.2f}s")
        return delay

    def add_retryable_exception(self, exception_type: Type[Exception]) -> None:
        """재시도 가능한 예외 타입 추가."""
        self.config.retryable_exceptions.add(exception_type)

    def add_retryable_status_code(self, status_code: int) -> None:
        """재시도할 HTTP 상태 코드 추가."""
        self.config.retry_on_status_codes.add(status_code)


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: Optional[Set[Type[Exception]]] = None,
):
    """
    재시도 데코레이터.

    사용 예:
        @with_retry(max_retries=3, base_delay=1.0)
        def call_external_service():
            ...
    """
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        retryable_exceptions=retryable_exceptions or DEFAULT_RETRYABLE_EXCEPTIONS.copy(),
    )
    policy = RetryPolicy(config)

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(policy.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if not policy.should_retry(e, attempt):
                        raise

                    delay = policy.get_delay(attempt)
                    logger.warning(
                        f"Retry {attempt + 1}/{policy.max_retries + 1} for {func.__name__} "
                        f"after {delay:.2f}s: {e}"
                    )
                    time.sleep(delay)

            # 모든 재시도 실패
            raise last_exception

        return wrapper

    return decorator


class RetryContext:
    """
    컨텍스트 매니저 스타일의 재시도.

    사용 예:
        retry = RetryContext(max_retries=3)
        while retry.should_continue():
            try:
                result = call_service()
                retry.success()
                return result
            except Exception as e:
                retry.failure(e)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        policy: Optional[RetryPolicy] = None,
    ):
        self.policy = policy or RetryPolicy(
            RetryConfig(max_retries=max_retries, base_delay=base_delay)
        )
        self._attempt = 0
        self._succeeded = False
        self._last_exception: Optional[Exception] = None

    @property
    def attempt(self) -> int:
        """현재 시도 횟수."""
        return self._attempt

    def should_continue(self) -> bool:
        """계속 시도해야 하는지 확인."""
        if self._succeeded:
            return False
        return self._attempt <= self.policy.max_retries

    def success(self) -> None:
        """성공 기록."""
        self._succeeded = True

    def failure(self, exception: Exception) -> None:
        """
        실패 기록 및 재시도 결정.

        재시도 불가능한 경우 예외를 다시 발생시킵니다.
        """
        self._last_exception = exception

        if not self.policy.should_retry(exception, self._attempt):
            raise exception

        delay = self.policy.get_delay(self._attempt)
        logger.warning(
            f"Retry {self._attempt + 1}/{self.policy.max_retries + 1}: "
            f"waiting {delay:.2f}s after {exception}"
        )
        time.sleep(delay)
        self._attempt += 1

        # 최대 재시도 초과
        if self._attempt > self.policy.max_retries:
            raise exception
