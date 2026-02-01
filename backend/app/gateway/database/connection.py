from typing import Generator
import os
import logging
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

class DatabaseConfig:
    """데이터베이스 설정."""

    def __init__(
        self,
        database_url: str = "",
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        query_timeout: int = 30,
        pool_pre_ping: bool = True,
    ):
        self.database_url = database_url
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.query_timeout = query_timeout
        self.pool_pre_ping = pool_pre_ping

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

# 전역 엔진 및 세션 팩토리
config = DatabaseConfig.from_env()

engine = create_engine(
    config.database_url,
    pool_size=config.pool_size,
    max_overflow=config.max_overflow,
    pool_timeout=config.pool_timeout,
    pool_pre_ping=config.pool_pre_ping,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
from sqlalchemy.orm import declarative_base
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency용 DB 세션 제너레이터."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def transaction() -> Generator[Session, None, None]:
    """
    트랜잭션 컨텍스트 매니저.
    자동으로 커밋/롤백을 처리합니다.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Transaction failed, rolled back: {e}")
        raise e
    finally:
        session.close()
