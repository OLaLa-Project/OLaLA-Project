"""
Embedding Gateway.

임베딩 서비스 호출을 관리하는 Gateway입니다.

Features:
- 배치 처리 최적화
- 부분 실패 재시도
- 연결 풀링
- 캐싱 지원
- Circuit Breaker
"""

import os
import json
import logging
import hashlib
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from threading import Lock
from collections import OrderedDict

import requests

from ..core.base_gateway import (
    BaseGateway,
    GatewayError,
    GatewayTimeoutError,
)
from ..core.circuit_breaker import CircuitBreakerConfig
from ..core.retry_policy import RetryConfig

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingConfig:
    """임베딩 설정."""

    ollama_url: str = ""
    """Ollama URL"""

    model: str = "nomic-embed-text"
    """임베딩 모델"""

    dimension: int = 768
    """임베딩 차원"""

    timeout_seconds: int = 60
    """요청 타임아웃"""

    batch_size: int = 64
    """배치 크기"""

    cache_size: int = 1000
    """캐시 크기"""

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        """환경 변수에서 설정 로드."""
        return cls(
            ollama_url=os.getenv("OLLAMA_URL", "http://ollama:11434"),
            model=os.getenv("EMBED_MODEL", "nomic-embed-text"),
            dimension=int(os.getenv("EMBED_DIM", "768")),
            timeout_seconds=int(os.getenv("OLLAMA_TIMEOUT", "60")),
            batch_size=int(os.getenv("EMBED_MISSING_BATCH", "64")),
            cache_size=int(os.getenv("EMBED_CACHE_SIZE", "1000")),
        )


class LRUCache:
    """간단한 LRU 캐시 구현."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: OrderedDict = OrderedDict()
        self.lock = Lock()

    def get(self, key: str) -> Optional[List[float]]:
        with self.lock:
            if key in self.cache:
                # 최근 사용으로 이동
                self.cache.move_to_end(key)
                return self.cache[key]
            return None

    def put(self, key: str, value: List[float]) -> None:
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            else:
                if len(self.cache) >= self.max_size:
                    self.cache.popitem(last=False)
                self.cache[key] = value

    def clear(self) -> None:
        with self.lock:
            self.cache.clear()

    @property
    def size(self) -> int:
        return len(self.cache)


class EmbeddingGateway(BaseGateway):
    """
    Embedding Gateway.

    임베딩 호출을 중앙에서 관리합니다.

    사용 예:
        gateway = EmbeddingGateway()

        # 단일 텍스트 임베딩
        embedding = gateway.embed_text("Hello, world!")

        # 배치 임베딩
        embeddings = gateway.embed_texts(["text1", "text2", "text3"])

        # 캐시 활용 임베딩
        embeddings = gateway.embed_texts_cached(texts)
    """

    def __init__(
        self,
        config: Optional[EmbeddingConfig] = None,
        circuit_config: Optional[CircuitBreakerConfig] = None,
        retry_config: Optional[RetryConfig] = None,
    ):
        # 기본 설정
        circuit_config = circuit_config or CircuitBreakerConfig(
            failure_threshold=5,
            timeout_seconds=30,
            success_threshold=2,
        )
        retry_config = retry_config or RetryConfig(
            max_retries=3,
            base_delay=0.5,
            max_delay=5.0,
        )

        super().__init__(
            name="embedding",
            circuit_config=circuit_config,
            retry_config=retry_config,
        )

        self.config = config or EmbeddingConfig.from_env()
        self._cache = LRUCache(max_size=self.config.cache_size)

        # 재시도 가능한 예외 추가
        self.retry_policy.add_retryable_exception(requests.exceptions.Timeout)
        self.retry_policy.add_retryable_exception(requests.exceptions.ConnectionError)

        logger.info(
            f"EmbeddingGateway initialized: model={self.config.model}, "
            f"dim={self.config.dimension}, batch_size={self.config.batch_size}"
        )

    def embed_text(self, text: str) -> List[float]:
        """
        단일 텍스트 임베딩.

        Args:
            text: 임베딩할 텍스트

        Returns:
            임베딩 벡터

        Raises:
            GatewayError: 임베딩 실패
        """
        embeddings = self.embed_texts([text])
        return embeddings[0] if embeddings else []

    def embed_texts(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
    ) -> List[List[float]]:
        """
        배치 텍스트 임베딩.

        Args:
            texts: 임베딩할 텍스트 리스트
            batch_size: 배치 크기 (기본값 사용 시 None)

        Returns:
            임베딩 벡터 리스트

        Raises:
            GatewayError: 임베딩 실패
        """
        if not texts:
            return []

        batch_size = batch_size or self.config.batch_size

        # 배치 분할
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            def operation():
                return self._embed_batch(batch)

            batch_embeddings = self.execute(operation, "embed_batch")
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def embed_texts_cached(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
    ) -> List[List[float]]:
        """
        캐시를 활용한 배치 임베딩.

        캐시에 있는 텍스트는 캐시에서 반환하고,
        없는 텍스트만 API 호출합니다.

        Args:
            texts: 임베딩할 텍스트 리스트
            batch_size: 배치 크기

        Returns:
            임베딩 벡터 리스트 (입력 순서 유지)
        """
        if not texts:
            return []

        # 캐시 확인
        results: List[Optional[List[float]]] = [None] * len(texts)
        texts_to_embed: List[Tuple[int, str]] = []

        for i, text in enumerate(texts):
            cache_key = self._make_cache_key(text)
            cached = self._cache.get(cache_key)

            if cached is not None:
                results[i] = cached
            else:
                texts_to_embed.append((i, text))

        # 캐시 미스 처리
        if texts_to_embed:
            indices, texts_only = zip(*texts_to_embed)

            new_embeddings = self.embed_texts(list(texts_only), batch_size)

            for idx, (orig_idx, text) in enumerate(texts_to_embed):
                embedding = new_embeddings[idx]
                results[orig_idx] = embedding

                # 캐시에 저장
                cache_key = self._make_cache_key(text)
                self._cache.put(cache_key, embedding)

        logger.debug(
            f"Cached embedding: {len(texts) - len(texts_to_embed)}/{len(texts)} cache hits"
        )

        return results

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """배치 임베딩 API 호출."""
        url = f"{self.config.ollama_url.rstrip('/')}/api/embed"

        payload = {
            "model": self.config.model,
            "input": texts,
        }

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()

            data = response.json()
            embeddings = data.get("embeddings", [])

            # 결과 검증
            if len(embeddings) != len(texts):
                logger.warning(
                    f"Embedding count mismatch: expected {len(texts)}, got {len(embeddings)}"
                )

            # 단일 임베딩인 경우 리스트로 감싸기
            if embeddings and isinstance(embeddings[0], (int, float)):
                embeddings = [embeddings]

            return embeddings

        except requests.exceptions.Timeout:
            raise GatewayTimeoutError(
                f"Embedding timeout after {self.config.timeout_seconds}s"
            )
        except requests.exceptions.RequestException as e:
            raise GatewayError(f"Embedding request failed: {e}", cause=e)

    def _make_cache_key(self, text: str) -> str:
        """캐시 키 생성."""
        return hashlib.md5(
            f"{self.config.model}:{text}".encode()
        ).hexdigest()

    def to_pgvector_literal(
        self,
        embedding: List[float],
        ndigits: int = 6,
    ) -> str:
        """
        임베딩을 pgvector 리터럴 형식으로 변환.

        Args:
            embedding: 임베딩 벡터
            ndigits: 소수점 자릿수

        Returns:
            pgvector 리터럴 문자열 (예: "[0.123,-0.456,...]")
        """
        return "[" + ",".join(f"{x:.{ndigits}f}" for x in embedding) + "]"

    def clear_cache(self) -> None:
        """캐시 초기화."""
        self._cache.clear()
        logger.info("Embedding cache cleared")

    @property
    def cache_stats(self) -> Dict[str, Any]:
        """캐시 통계."""
        return {
            "size": self._cache.size,
            "max_size": self.config.cache_size,
        }


# 전역 EmbeddingGateway 인스턴스
_embedding_gateway: Optional[EmbeddingGateway] = None


def get_embedding_gateway() -> EmbeddingGateway:
    """전역 EmbeddingGateway 반환."""
    global _embedding_gateway
    if _embedding_gateway is None:
        _embedding_gateway = EmbeddingGateway()
    return _embedding_gateway
