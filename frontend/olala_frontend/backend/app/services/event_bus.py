import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class RedisEventBus:
    def __init__(self, redis_url: str, channel: str) -> None:
        self._redis_url = redis_url
        self._channel = channel
        self._publisher: redis.Redis | None = None
        self._subscriber: redis.Redis | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def start(self, handler: EventHandler) -> None:
        if self._listener_task is not None:
            return

        self._publisher = redis.from_url(self._redis_url, decode_responses=True)
        self._subscriber = redis.from_url(self._redis_url, decode_responses=True)
        self._stop_event.clear()
        self._listener_task = asyncio.create_task(self._listen_loop(handler))

    async def stop(self) -> None:
        self._stop_event.set()

        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None

        if self._publisher is not None:
            await self._publisher.aclose()
            self._publisher = None

        if self._subscriber is not None:
            await self._subscriber.aclose()
            self._subscriber = None

    async def publish(self, payload: dict[str, Any]) -> bool:
        if self._publisher is None:
            return False

        try:
            await self._publisher.publish(
                self._channel,
                json.dumps(payload, ensure_ascii=False),
            )
            return True
        except Exception:
            logger.exception("Failed to publish redis event")
            return False

    async def _listen_loop(self, handler: EventHandler) -> None:
        if self._subscriber is None:
            return

        while not self._stop_event.is_set():
            pubsub = self._subscriber.pubsub()
            try:
                await pubsub.subscribe(self._channel)
                while not self._stop_event.is_set():
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                    if not message:
                        await asyncio.sleep(0.05)
                        continue

                    raw_data = message.get("data")
                    if not isinstance(raw_data, str):
                        continue

                    try:
                        event = json.loads(raw_data)
                    except json.JSONDecodeError:
                        logger.warning("Dropped invalid redis event: %s", raw_data)
                        continue

                    if not isinstance(event, dict):
                        continue

                    try:
                        await handler(event)
                    except Exception:
                        logger.exception("Redis event handler failed")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Redis listener disconnected, retrying")
                await asyncio.sleep(1.0)
            finally:
                await pubsub.unsubscribe(self._channel)
                await pubsub.aclose()
