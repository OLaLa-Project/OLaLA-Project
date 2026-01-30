"""
External API Gateway.

외부 API 호출을 관리하는 Gateway입니다.

Features:
- Rate Limiting
- 재시도 정책
- 로깅 및 메트릭
- 폴백 처리
"""

import os
import logging
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from threading import Lock
from abc import ABC, abstractmethod

import requests

from ..core.base_gateway import (
    BaseGateway,
    GatewayError,
    GatewayTimeoutError,
)
from ..core.circuit_breaker import CircuitBreakerConfig
from ..core.retry_policy import RetryConfig
from ..schemas import EvidenceCandidate, SourceType

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate Limiter 구현."""

    def __init__(self, max_requests: int, window_seconds: int = 60):
        """
        Args:
            max_requests: 윈도우 내 최대 요청 수
            window_seconds: 윈도우 크기 (초)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: List[float] = []
        self.lock = Lock()

    def acquire(self) -> bool:
        """
        요청 허용 여부 확인 및 요청 등록.

        Returns:
            True: 허용됨
            False: Rate limit 초과
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self.lock:
            # 만료된 요청 제거
            self.requests = [t for t in self.requests if t > window_start]

            # 허용 여부 확인
            if len(self.requests) >= self.max_requests:
                return False

            # 요청 등록
            self.requests.append(now)
            return True

    def wait_if_needed(self) -> float:
        """
        Rate limit 초과 시 대기.

        Returns:
            대기 시간 (초)
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self.lock:
            self.requests = [t for t in self.requests if t > window_start]

            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return 0.0

            # 가장 오래된 요청이 만료될 때까지 대기
            oldest = min(self.requests)
            wait_time = oldest + self.window_seconds - now

            if wait_time > 0:
                time.sleep(wait_time)

            self.requests.append(time.time())
            return wait_time


class ExternalSearchClient(ABC):
    """외부 검색 클라이언트 기본 클래스."""

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """검색 수행."""
        pass


@dataclass
class NaverConfig:
    """Naver API 설정."""

    client_id: str = ""
    client_secret: str = ""
    timeout_seconds: int = 10
    max_requests_per_day: int = 25000

    @classmethod
    def from_env(cls) -> "NaverConfig":
        return cls(
            client_id=os.getenv("NAVER_CLIENT_ID", ""),
            client_secret=os.getenv("NAVER_CLIENT_SECRET", ""),
            timeout_seconds=int(os.getenv("NAVER_TIMEOUT", "10")),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


class NaverNewsClient(ExternalSearchClient):
    """Naver News API 클라이언트."""

    def __init__(self, config: Optional[NaverConfig] = None):
        self.config = config or NaverConfig.from_env()
        self.rate_limiter = RateLimiter(
            max_requests=100,  # 분당 100회
            window_seconds=60,
        )

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Naver 뉴스 검색.

        Args:
            query: 검색어
            max_results: 최대 결과 수

        Returns:
            검색 결과 리스트
        """
        if not self.config.is_configured:
            logger.warning("Naver API credentials not configured")
            return []

        # Rate limiting
        if not self.rate_limiter.acquire():
            logger.warning("Naver API rate limit exceeded")
            return []

        # 쿼리 정제
        safe_query = (query or "").strip()
        if len(safe_query) > 100:
            safe_query = safe_query[:100]

        url = "https://openapi.naver.com/v1/search/news.json"
        headers = {
            "X-Naver-Client-Id": self.config.client_id,
            "X-Naver-Client-Secret": self.config.client_secret,
        }
        params = {
            "query": safe_query,
            "display": min(max_results, 10),
            "sort": "sim",
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()

            data = response.json()
            results = []

            for item in data.get("items", []):
                # HTML 태그 제거
                title = self._clean_html(item.get("title", ""))
                description = self._clean_html(item.get("description", ""))

                results.append({
                    "source_type": SourceType.NEWS.value,
                    "title": title,
                    "url": item.get("link", ""),
                    "content": description,
                    "metadata": {
                        "origin": "naver",
                        "pub_date": item.get("pubDate"),
                    },
                })

            logger.debug(f"Naver search returned {len(results)} results for '{query}'")
            return results

        except requests.exceptions.Timeout:
            logger.error(f"Naver API timeout for query: {query}")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Naver API error: {e}")
            return []

    @staticmethod
    def _clean_html(text: str) -> str:
        """HTML 태그 제거."""
        import re
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&quot;", '"')
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        return text


class DuckDuckGoClient(ExternalSearchClient):
    """DuckDuckGo 검색 클라이언트."""

    def __init__(self, timeout_seconds: int = 10):
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        DuckDuckGo 검색.

        Args:
            query: 검색어
            max_results: 최대 결과 수

        Returns:
            검색 결과 리스트
        """
        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                ddg_results = list(ddgs.text(query, max_results=max_results))

            results = []
            for r in ddg_results:
                results.append({
                    "source_type": SourceType.WEB.value,
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "content": r.get("body", ""),
                    "metadata": {"origin": "duckduckgo"},
                })

            logger.debug(f"DuckDuckGo search returned {len(results)} results for '{query}'")
            return results

        except ImportError:
            logger.error("duckduckgo_search package not installed")
            return []
        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return []


class ExternalAPIGateway(BaseGateway):
    """
    External API Gateway.

    외부 API 호출을 중앙에서 관리합니다.

    사용 예:
        gateway = ExternalAPIGateway()

        # Naver 뉴스 검색
        news = gateway.search_naver_news("검색어")

        # DuckDuckGo 검색
        web = gateway.search_duckduckgo("검색어")

        # 통합 검색 (모든 소스)
        results = gateway.search_all("검색어")
    """

    def __init__(
        self,
        naver_config: Optional[NaverConfig] = None,
        circuit_config: Optional[CircuitBreakerConfig] = None,
        retry_config: Optional[RetryConfig] = None,
    ):
        circuit_config = circuit_config or CircuitBreakerConfig(
            failure_threshold=5,
            timeout_seconds=30,
        )
        retry_config = retry_config or RetryConfig(
            max_retries=2,
            base_delay=0.5,
            max_delay=5.0,
        )

        super().__init__(
            name="external_api",
            circuit_config=circuit_config,
            retry_config=retry_config,
        )

        self.naver_client = NaverNewsClient(naver_config)
        self.ddg_client = DuckDuckGoClient()

        logger.info("ExternalAPIGateway initialized")

    def search_naver_news(
        self,
        query: str,
        max_results: int = 5,
    ) -> List[EvidenceCandidate]:
        """
        Naver 뉴스 검색.

        Args:
            query: 검색어
            max_results: 최대 결과 수

        Returns:
            EvidenceCandidate 리스트
        """
        def operation():
            return self.naver_client.search(query, max_results)

        try:
            raw_results = self.execute(operation, "naver_news")
            return [EvidenceCandidate.from_raw(r) for r in raw_results]
        except GatewayError as e:
            logger.warning(f"Naver search failed: {e}")
            return []

    def search_duckduckgo(
        self,
        query: str,
        max_results: int = 5,
    ) -> List[EvidenceCandidate]:
        """
        DuckDuckGo 검색.

        Args:
            query: 검색어
            max_results: 최대 결과 수

        Returns:
            EvidenceCandidate 리스트
        """
        def operation():
            return self.ddg_client.search(query, max_results)

        try:
            raw_results = self.execute(operation, "duckduckgo")
            return [EvidenceCandidate.from_raw(r) for r in raw_results]
        except GatewayError as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            return []

    def search_all(
        self,
        query: str,
        max_results_per_source: int = 5,
    ) -> List[EvidenceCandidate]:
        """
        모든 소스에서 통합 검색.

        Args:
            query: 검색어
            max_results_per_source: 소스당 최대 결과 수

        Returns:
            모든 소스의 결과를 합친 EvidenceCandidate 리스트
        """
        all_results = []

        # Naver News
        naver_results = self.search_naver_news(query, max_results_per_source)
        all_results.extend(naver_results)

        # DuckDuckGo
        ddg_results = self.search_duckduckgo(query, max_results_per_source)
        all_results.extend(ddg_results)

        logger.info(
            f"External search for '{query}': "
            f"naver={len(naver_results)}, ddg={len(ddg_results)}"
        )

        return all_results


# 전역 ExternalAPIGateway 인스턴스
_external_gateway: Optional[ExternalAPIGateway] = None


def get_external_gateway() -> ExternalAPIGateway:
    """전역 ExternalAPIGateway 반환."""
    global _external_gateway
    if _external_gateway is None:
        _external_gateway = ExternalAPIGateway()
    return _external_gateway
