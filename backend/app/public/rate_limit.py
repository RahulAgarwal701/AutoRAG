import time
import uuid
from dataclasses import dataclass
from functools import lru_cache

from redis.asyncio import Redis

from app.core.config import get_settings

_SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local reset_at = now + window
  if oldest[2] then reset_at = tonumber(oldest[2]) + window end
  return {0, 0, reset_at}
end
redis.call('ZADD', key, now, member)
redis.call('PEXPIRE', key, window)
return {1, limit - count - 1, now + window}
"""


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_at_ms: int


class SlidingWindowRateLimiter:
    def __init__(self, redis: Redis, window_seconds: int) -> None:
        self._redis = redis
        self._window_ms = window_seconds * 1000

    async def check(self, identifier: str, limit: int) -> RateLimitResult:
        now_ms = int(time.time() * 1000)
        result = await self._redis.eval(
            _SLIDING_WINDOW_SCRIPT,
            1,
            f"autorag:rate:{identifier}",
            now_ms,
            self._window_ms,
            limit,
            f"{now_ms}:{uuid.uuid4()}",
        )
        allowed, remaining, reset_at_ms = (int(value) for value in result)
        return RateLimitResult(bool(allowed), remaining, reset_at_ms)


@lru_cache
def get_rate_limiter() -> SlidingWindowRateLimiter:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return SlidingWindowRateLimiter(redis, settings.rate_limit_window_seconds)
