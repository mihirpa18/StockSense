"""
Run this from backend/ with your real .env in place:
    python diagnose_redis_connection.py

Prints exactly what's wrong without ever printing your password.
"""
import os
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv
load_dotenv()

url = os.environ.get("REDIS_URL", "")
if not url:
    print("REDIS_URL is not set in your .env at all.")
    sys.exit(1)

parsed = urlparse(url)
redacted = f"{parsed.scheme}://{parsed.username}:***@{parsed.hostname}:{parsed.port}"
print(f"Parsed REDIS_URL: {redacted}")

if parsed.scheme != "rediss":
    print(f"\n>>> FOUND IT: scheme is '{parsed.scheme}', should be 'rediss' (with two s's).")
    print(">>> Upstash's TCP port is TLS-only — 'redis://' connects, then gets dropped")
    print(">>> the instant it tries to speak plaintext protocol instead of TLS.")
    sys.exit(1)

print("Scheme is correct (rediss). Testing actual connection...")
import redis
try:
    r = redis.from_url(url, decode_responses=True, socket_connect_timeout=5)
    result = r.ping()
    print(f"SUCCESS — ping() returned {result}")
except redis.exceptions.AuthenticationError:
    print("\n>>> Connected over TLS fine, but the PASSWORD is wrong.")
    print(">>> Re-copy it from the Upstash console's redis-py tab — check for a")
    print(">>> trailing space or a copy-paste truncation.")
except redis.exceptions.ConnectionError as e:
    print(f"\n>>> Still failing even with correct scheme: {e}")
    print(">>> Possible causes: wrong hostname/port, or the database was")
    print(">>> paused/deleted in the Upstash console — check it's shown as Active there.")