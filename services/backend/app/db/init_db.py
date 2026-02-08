from sqlalchemy import text

from app.db.session import Base, engine
from app.db import models  # noqa: F401


def init_db() -> None:
    # pgvector 타입 의존 테이블 생성 전에 확장을 보장한다.
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
