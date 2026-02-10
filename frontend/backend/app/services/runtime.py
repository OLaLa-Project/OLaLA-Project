from app.core.config import settings

from .event_bus import RedisEventBus
from .realtime import RealtimeManager

realtime_manager = RealtimeManager()
event_bus = RedisEventBus(
    redis_url=settings.redis_url,
    channel=settings.redis_channel,
)
