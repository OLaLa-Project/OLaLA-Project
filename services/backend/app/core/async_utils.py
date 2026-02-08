from __future__ import annotations

import asyncio
import threading
from queue import Queue
from typing import Callable, Coroutine, TypeVar, cast

T = TypeVar("T")


def run_async_in_sync(async_fn: Callable[..., Coroutine[object, object, T]], *args: object, **kwargs: object) -> T:
    """
    Execute an async function from sync code safely.

    - No running loop in current thread: use asyncio.run directly.
    - Running loop exists: execute in a dedicated background thread with its own loop.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(async_fn(*args, **kwargs))

    result_queue: Queue[tuple[bool, object]] = Queue(maxsize=1)

    def _worker() -> None:
        try:
            result: T = asyncio.run(async_fn(*args, **kwargs))
            result_queue.put((True, result))
        except Exception as exc:  # pragma: no cover - error path passthrough
            result_queue.put((False, exc))

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join()

    ok, payload = result_queue.get()
    if ok:
        return cast(T, payload)
    raise cast(Exception, payload)
