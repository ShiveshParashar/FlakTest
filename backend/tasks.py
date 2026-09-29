import json

from .database import SessionLocal
from .flaky_detector import get_flaky_tests
from .redis_client import get_redis

CACHE_TTL_SECONDS = 300


def flaky_tests_cache_key(repository: str) -> str:
    return f"flaky_tests:{repository}"


def recompute_flaky_tests(repository: str) -> None:
    """Background job: recompute flaky tests for a repository and cache
    the result in Redis so API/dashboard reads are cheap."""

    db = SessionLocal()

    try:
        results = get_flaky_tests(db, repository=repository)
    finally:
        db.close()

    payload = json.dumps(results, default=str)

    redis_conn = get_redis()

    if redis_conn is not None:
        redis_conn.setex(
            flaky_tests_cache_key(repository),
            CACHE_TTL_SECONDS,
            payload,
        )
