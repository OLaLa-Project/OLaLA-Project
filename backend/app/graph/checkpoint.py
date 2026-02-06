import logging
import re
import time
from threading import Lock
from typing import Any

from app.core.settings import settings
from app.db.session import engine
from sqlalchemy import text

logger = logging.getLogger(__name__)

_checkpoint_lock = Lock()
_thread_last_seen: dict[str, float] = {}
_checkpointer_initialized = False
_checkpointer_instance: Any | None = None
_thread_table_ready = False


def _effective_backend() -> str:
    if not settings.checkpoint_enabled:
        return "none"
    return settings.checkpoint_backend


def _ttl_seconds() -> int:
    return max(0, int(settings.checkpoint_ttl_seconds))


def _prune_expired_threads(now: float) -> None:
    ttl = _ttl_seconds()
    if ttl <= 0:
        return
    expired_ids = [tid for tid, ts in _thread_last_seen.items() if (now - ts) > ttl]
    for thread_id in expired_ids:
        _thread_last_seen.pop(thread_id, None)


def _thread_table_name() -> str:
    table = (settings.checkpoint_thread_table or "checkpoint_threads").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        return "checkpoint_threads"
    return table


def _ensure_thread_table_exists() -> None:
    global _thread_table_ready
    if _thread_table_ready:
        return
    table = _thread_table_name()
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    thread_id TEXT PRIMARY KEY,
                    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
    _thread_table_ready = True


def _resolve_thread_id_with_postgres(
    requested_thread_id: str | None,
    fallback_thread_id: str,
    now: float,
) -> tuple[str, bool, bool]:
    requested = (requested_thread_id or "").strip()
    ttl = _ttl_seconds()
    table = _thread_table_name()
    _ensure_thread_table_exists()

    with engine.begin() as conn:
        if not requested:
            if ttl > 0:
                conn.execute(
                    text(
                        f"""
                        DELETE FROM {table}
                        WHERE EXTRACT(EPOCH FROM (NOW() - last_seen)) > :ttl_seconds
                        """
                    ),
                    {"ttl_seconds": float(ttl)},
                )
            conn.execute(
                text(
                    f"""
                    INSERT INTO {table}(thread_id, last_seen)
                    VALUES (:thread_id, NOW())
                    ON CONFLICT(thread_id) DO UPDATE SET last_seen=EXCLUDED.last_seen
                    """
                ),
                {"thread_id": fallback_thread_id},
            )
            return fallback_thread_id, False, False

        row = conn.execute(
            text(
                f"""
                SELECT EXTRACT(EPOCH FROM (NOW() - last_seen)) AS age_seconds
                FROM {table}
                WHERE thread_id = :thread_id
                """
            ),
            {"thread_id": requested},
        ).fetchone()
        age_seconds = float(row[0]) if row else None

        if age_seconds is not None and ttl > 0 and age_seconds > ttl:
            conn.execute(
                text(f"DELETE FROM {table} WHERE thread_id = :thread_id"),
                {"thread_id": requested},
            )
            conn.execute(
                text(
                    f"""
                    INSERT INTO {table}(thread_id, last_seen)
                    VALUES (:thread_id, NOW())
                    ON CONFLICT(thread_id) DO UPDATE SET last_seen=EXCLUDED.last_seen
                    """
                ),
                {"thread_id": fallback_thread_id},
            )
            if ttl > 0:
                conn.execute(
                    text(
                        f"""
                        DELETE FROM {table}
                        WHERE thread_id != :keep_id
                          AND EXTRACT(EPOCH FROM (NOW() - last_seen)) > :ttl_seconds
                        """
                    ),
                    {"keep_id": fallback_thread_id, "ttl_seconds": float(ttl)},
                )
            return fallback_thread_id, False, True

        conn.execute(
            text(
                f"""
                INSERT INTO {table}(thread_id, last_seen)
                VALUES (:thread_id, NOW())
                ON CONFLICT(thread_id) DO UPDATE SET last_seen=EXCLUDED.last_seen
                """
            ),
            {"thread_id": requested},
        )
        if ttl > 0:
            conn.execute(
                text(
                    f"""
                    DELETE FROM {table}
                    WHERE thread_id != :keep_id
                      AND EXTRACT(EPOCH FROM (NOW() - last_seen)) > :ttl_seconds
                    """
                ),
                {"keep_id": requested, "ttl_seconds": float(ttl)},
            )
        return requested, True, False


def resolve_checkpoint_thread_id(
    requested_thread_id: str | None,
    fallback_thread_id: str,
) -> tuple[str, bool, bool]:
    """
    Resolve thread_id for checkpointed runs.

    Returns (thread_id, resumed, expired).
    """
    backend = _effective_backend()
    if backend == "none":
        return fallback_thread_id, False, False

    now = time.time()
    if backend == "postgres":
        try:
            return _resolve_thread_id_with_postgres(requested_thread_id, fallback_thread_id, now)
        except Exception as exc:  # pragma: no cover - runtime safeguard
            logger.warning("PostgreSQL checkpoint thread store unavailable, fallback to memory: %s", exc)

    requested = (requested_thread_id or "").strip()
    with _checkpoint_lock:
        if not requested:
            _prune_expired_threads(now)
            _thread_last_seen[fallback_thread_id] = now
            return fallback_thread_id, False, False

        last_seen = _thread_last_seen.get(requested)
        ttl = _ttl_seconds()
        if last_seen is not None and ttl > 0 and (now - last_seen) > ttl:
            _thread_last_seen.pop(requested, None)
            _prune_expired_threads(now)
            _thread_last_seen[fallback_thread_id] = now
            return fallback_thread_id, False, True

        _prune_expired_threads(now)
        _thread_last_seen[requested] = now
        return requested, True, False


def get_graph_checkpointer() -> Any | None:
    backend = _effective_backend()
    if backend == "none":
        return None

    global _checkpointer_initialized
    global _checkpointer_instance

    with _checkpoint_lock:
        if _checkpointer_initialized:
            return _checkpointer_instance

        if backend == "postgres":
            _checkpointer_instance = _build_postgres_checkpointer()
        else:
            _checkpointer_instance = _build_memory_checkpointer()

        _checkpointer_initialized = True
        return _checkpointer_instance


def _build_memory_checkpointer() -> Any | None:
    try:
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("Failed to initialize MemorySaver checkpointer: %s", exc)
        return None


def _build_postgres_checkpointer() -> Any | None:
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("PostgresSaver not available (%s); fallback to memory backend.", exc)
        return _build_memory_checkpointer()

    conn_str = settings.database_url_resolved
    if hasattr(PostgresSaver, "from_conn_string"):
        for candidate in (conn_str, conn_str.replace("postgresql://", "postgres://", 1)):
            try:
                saver = PostgresSaver.from_conn_string(candidate)
                if saver is not None:
                    if hasattr(saver, "setup"):
                        saver.setup()
                    return saver
            except Exception:
                continue

    try:
        saver = PostgresSaver(conn_str)
        if hasattr(saver, "setup"):
            saver.setup()
        return saver
    except Exception as exc:
        logger.warning("Failed to initialize PostgresSaver (%s); fallback to memory backend.", exc)
        return _build_memory_checkpointer()


def reset_checkpoint_runtime_for_test() -> None:
    """Test-only helper to clear singleton/cache state."""
    global _checkpointer_initialized
    global _checkpointer_instance
    global _thread_table_ready
    with _checkpoint_lock:
        _thread_last_seen.clear()
        _checkpointer_initialized = False
        _checkpointer_instance = None
        _thread_table_ready = False
