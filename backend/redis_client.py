import os

import redis
from rq import Queue

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

redis_conn = redis.from_url(REDIS_URL)
task_queue = Queue("flakeguard", connection=redis_conn)


def get_redis():
    """Return the Redis connection, or None if Redis is unreachable.

    Redis is used as a best-effort cache and job queue: the API must keep
    working (falling back to live DB queries) even if Redis is down.
    """
    try:
        redis_conn.ping()
        return redis_conn
    except redis.RedisError:
        return None
