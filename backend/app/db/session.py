from app.gateway.database.connection import engine, SessionLocal, Base, get_db

# Shim for legacy imports
__all__ = ["engine", "SessionLocal", "Base", "get_db"]
