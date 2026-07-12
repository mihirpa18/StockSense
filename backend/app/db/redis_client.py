import redis
from app.config import settings

# Sync client, matching the sync call pattern used in services/llm.py and
# services/embedder.py — those run inside asyncio.to_thread() at the router
# boundary, so a blocking Redis client here is fine and simpler than mixing
# async Redis into otherwise-sync service functions.
_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        # decode_responses=True: get str back instead of bytes, matches how
        # the rest of the codebase handles strings (e.g. Supabase client).
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client