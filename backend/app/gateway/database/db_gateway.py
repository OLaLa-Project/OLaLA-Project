"""
Database Gateway.

데이터베이스 작업을 관리하는 Gateway입니다.

Features:
- 트랜잭션 관리
- 쿼리 타임아웃
- 연결 풀 관리
- 재시도 정책
- 메트릭 수집
"""

import os
import logging
import time
from typing import Optional, List, Dict, Any, Callable, TypeVar
from dataclasses import dataclass
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError

from ..core.base_gateway import (
    BaseGateway,
    GatewayError,
    GatewayTimeoutError,
)
from ..core.circuit_breaker import CircuitBreakerConfig
from ..core.retry_policy import RetryConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class DatabaseConfig:
    """데이터베이스 설정."""

    database_url: str = ""
    """Database URL"""

    pool_size: int = 5
    """연결 풀 크기"""

    max_overflow: int = 10
    """최대 초과 연결 수"""

    pool_timeout: int = 30
    """풀 대기 타임아웃 (초)"""

    query_timeout: int = 30
    """쿼리 타임아웃 (초)"""

    pool_pre_ping: bool = True
    """연결 사전 확인 여부"""

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """환경 변수에서 설정 로드."""
        db_host = os.getenv("DB_HOST", "db")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "olala")
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "postgres")

        database_url = os.getenv(
            "DATABASE_URL",
            f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        )

        return cls(
            database_url=database_url,
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
            query_timeout=int(os.getenv("DB_QUERY_TIMEOUT", "30")),
        )


class DatabaseGateway(BaseGateway):
    """
    Database Gateway.

    데이터베이스 작업을 중앙에서 관리합니다.

    사용 예:
        gateway = DatabaseGateway()

        # 트랜잭션 내에서 작업
        with gateway.transaction() as session:
            result = session.execute(text("SELECT * FROM users"))

        # 쿼리 실행 (자동 재시도)
        results = gateway.execute_query("SELECT * FROM users WHERE id = :id", {"id": 1})

        # 벡터 검색
        results = gateway.vector_search(embedding, top_k=5)
    """

    def __init__(
        self,
        config: Optional[DatabaseConfig] = None,
        circuit_config: Optional[CircuitBreakerConfig] = None,
        retry_config: Optional[RetryConfig] = None,
    ):
        circuit_config = circuit_config or CircuitBreakerConfig(
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2,
        )
        retry_config = retry_config or RetryConfig(
            max_retries=3,
            base_delay=0.5,
            max_delay=5.0,
        )

        super().__init__(
            name="database",
            circuit_config=circuit_config,
            retry_config=retry_config,
        )

        self.config = config or DatabaseConfig.from_env()

        # SQLAlchemy 엔진 생성
        self._engine = create_engine(
            self.config.database_url,
            pool_size=self.config.pool_size,
            max_overflow=self.config.max_overflow,
            pool_timeout=self.config.pool_timeout,
            pool_pre_ping=self.config.pool_pre_ping,
        )
        self._session_factory = sessionmaker(bind=self._engine)

        # 재시도 가능한 예외 추가
        self.retry_policy.add_retryable_exception(OperationalError)

        logger.info(
            f"DatabaseGateway initialized: pool_size={self.config.pool_size}, "
            f"query_timeout={self.config.query_timeout}s"
        )

    @contextmanager
    def transaction(self):
        """
        트랜잭션 컨텍스트 매니저.

        자동으로 커밋/롤백을 처리합니다.

        사용 예:
            with gateway.transaction() as session:
                session.execute(text("INSERT INTO ..."))
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Transaction failed, rolled back: {e}")
            raise GatewayError(f"Transaction failed: {e}", cause=e)
        finally:
            session.close()

    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        SQL 쿼리 실행.

        Args:
            query: SQL 쿼리 문자열
            params: 쿼리 파라미터

        Returns:
            결과 딕셔너리 리스트
        """
        def operation():
            with self.transaction() as session:
                # 타임아웃 설정
                session.execute(
                    text(f"SET statement_timeout = '{self.config.query_timeout * 1000}'")
                )

                result = session.execute(text(query), params or {})

                # SELECT 쿼리인 경우 결과 반환
                if result.returns_rows:
                    columns = result.keys()
                    return [dict(zip(columns, row)) for row in result.fetchall()]

                return []

        return self.execute(operation, "execute_query")

    def execute_many(
        self,
        query: str,
        params_list: List[Dict[str, Any]],
    ) -> int:
        """
        여러 파라미터로 쿼리 일괄 실행.

        Args:
            query: SQL 쿼리 문자열
            params_list: 파라미터 딕셔너리 리스트

        Returns:
            영향받은 행 수
        """
        def operation():
            with self.transaction() as session:
                total_affected = 0
                for params in params_list:
                    result = session.execute(text(query), params)
                    total_affected += result.rowcount
                return total_affected

        return self.execute(operation, "execute_many")

    def vector_search(
        self,
        embedding: List[float],
        table: str = "wiki_chunks",
        column: str = "embedding",
        top_k: int = 5,
        where_clause: str = "",
    ) -> List[Dict[str, Any]]:
        """
        벡터 유사도 검색.

        Args:
            embedding: 검색 벡터
            table: 테이블 이름
            column: 벡터 컬럼 이름
            top_k: 반환할 결과 수
            where_clause: 추가 WHERE 조건

        Returns:
            검색 결과 리스트
        """
        # 임베딩을 pgvector 형식으로 변환
        embedding_str = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"

        where = f"WHERE {where_clause}" if where_clause else ""

        query = f"""
            SELECT *, ({column} <=> :embedding::vector) as distance
            FROM {table}
            {where}
            ORDER BY {column} <=> :embedding::vector
            LIMIT :top_k
        """

        def operation():
            with self.transaction() as session:
                result = session.execute(
                    text(query),
                    {"embedding": embedding_str, "top_k": top_k}
                )
                columns = result.keys()
                return [dict(zip(columns, row)) for row in result.fetchall()]

        return self.execute(operation, "vector_search")

    def check_health(self) -> Dict[str, Any]:
        """
        데이터베이스 연결 상태 확인.

        Returns:
            상태 정보 딕셔너리
        """
        try:
            start = time.time()
            with self.transaction() as session:
                session.execute(text("SELECT 1"))
            latency = (time.time() - start) * 1000

            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "pool_size": self._engine.pool.size(),
                "pool_checkedin": self._engine.pool.checkedin(),
                "pool_checkedout": self._engine.pool.checkedout(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    def dispose(self) -> None:
        """연결 풀 종료."""
        self._engine.dispose()
        logger.info("Database connection pool disposed")


# 전역 DatabaseGateway 인스턴스
_db_gateway: Optional[DatabaseGateway] = None


def get_db_gateway() -> DatabaseGateway:
    """전역 DatabaseGateway 반환."""
    global _db_gateway
    if _db_gateway is None:
        _db_gateway = DatabaseGateway()
    return _db_gateway
