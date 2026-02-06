from app.gateway.database.connection import engine, SessionLocal, Base, get_db

def init_db():
    """데이터베이스 테이블 생성."""
    Base.metadata.create_all(bind=engine)

# Shim for legacy imports
__all__ = ["engine", "SessionLocal", "Base", "get_db", "init_db"]
