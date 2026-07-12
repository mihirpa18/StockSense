"""
Redis-backed token bucket rate limiter for outbound Gemini (chat) and
Mistral (embeddings) calls.

Two separate buckets by design: Gemini and Mistral have independent
RPM/TPM limits on their own dashboards, so a single shared bucket would
either under- or over-throttle one of them.

Atomicity: the check-and-decrement happens inside a single Lua script,
so concurrent calls (e.g. multiple asyncio.to_thread workers, or later,
multiple arq worker jobs) can't both read "1 token left" and both proceed.
Verified locally against a real Redis instance, including a 20-thread
concurrency test against a 5-token bucket (see chat history / commit note).
"""
import time
from app.db.redis_client import get_redis
from app.utils.logger import logger

_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local bucket = redis.call("HMGET", key, "tokens", "last_refill")
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    last_refill = now
end

local elapsed = math.max(0, now - last_refill)
tokens = math.min(capacity, tokens + elapsed * refill_rate)

local allowed = 0
if tokens >= requested then
    tokens = tokens - requested
    allowed = 1
end

redis.call("HMSET", key, "tokens", tokens, "last_refill", now)
redis.call("EXPIRE", key, 3600)

return {allowed, tostring(tokens)}
"""

_script = None


def _get_script():
    global _script
    if _script is None:
        _script = get_redis().register_script(_TOKEN_BUCKET_LUA)
    return _script


class RateLimitExceeded(Exception):
    """Raised only if a bucket is still empty after acquire() has already
    blocked and polled for up to max_wait_seconds — acquire() handles the
    "wait for refill" case internally, so this is the genuine last-resort
    failure, not something that needs an external retry wrapper.

    Small bonus: the message contains "rate limit", so if this does bubble
    up through embedder.py's get_embeddings_batch() (which retries on any
    exception matching that phrase), it gets one more retry pass for free —
    but that's incidental, not something the design depends on.
    """
    pass


# --- Bucket capacity / refill rate ------------------------------------
# TODO(mihir): these are placeholders. Check your actual RPM/TPM limits on
# the Mistral and Gemini dashboards and replace these before relying on
# this in anything resembling production. Wrong numbers here either
# throttle you for no reason or don't protect you at all.
GEMINI_CHAT_CAPACITY = 5          # max tokens (i.e. max burst of calls)
GEMINI_CHAT_REFILL_RATE = 5/60     # tokens/sec added back (~15/min)

MISTRAL_EMBED_CAPACITY = 1
MISTRAL_EMBED_REFILL_RATE = 1.0    # ~60/min


def acquire(bucket_name: str, capacity: float, refill_rate: float,
            tokens_requested: int = 1, max_wait_seconds: float = 30,
            poll_interval: float = 0.5) -> None:
    """
    Blocks (via time.sleep, safe here since callers run inside
    asyncio.to_thread) until a token is available, or raises
    RateLimitExceeded after max_wait_seconds.
    """
    key = f"ratelimit:{bucket_name}"
    script = _get_script()
    deadline = time.time() + max_wait_seconds

    while True:
        allowed, remaining = script(
            keys=[key], args=[capacity, refill_rate, time.time(), tokens_requested]
        )
        if allowed:
            return
        remaining_wait = deadline - time.time()
        if remaining_wait <= 0:
            logger.warning(
                f"Rate limit exceeded for bucket '{bucket_name}' after waiting {max_wait_seconds}s"
            )
            raise RateLimitExceeded(f"Rate limit exceeded for {bucket_name}")
        # Never sleep past the deadline — a fixed poll_interval could
        # otherwise overshoot max_wait_seconds by up to poll_interval,
        # letting a token that regenerated *after* the intended cutoff
        # sneak through on the next check.
        time.sleep(min(poll_interval, remaining_wait))