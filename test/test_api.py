import hashlib
import hmac
import os

os.environ.setdefault("FLAKEGUARD_API_KEY", "test-secret")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app

API_KEY = os.environ["FLAKEGUARD_API_KEY"]
WEBHOOK_SECRET = os.environ["GITHUB_WEBHOOK_SECRET"]

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _post_ci_result(repository, commit_sha, test_outcomes):
    return client.post(
        "/api/v1/ci/test-results",
        json={
            "repository": repository,
            "commit_sha": commit_sha,
            "branch": "main",
            "total_tests": len(test_outcomes),
            "passed": sum(1 for o in test_outcomes.values() if o == "passed"),
            "failed": sum(1 for o in test_outcomes.values() if o == "failed"),
            "skipped": 0,
            "test_results": [
                {"test_name": name, "outcome": outcome, "duration": 0.01}
                for name, outcome in test_outcomes.items()
            ],
        },
        headers={"X-API-Key": API_KEY},
    )


def _github_signature(body: bytes) -> str:
    digest = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_rejects_missing_api_key():
    response = client.post(
        "/api/v1/ci/test-results",
        json={
            "repository": "r", "commit_sha": "c", "branch": "b",
            "total_tests": 0, "passed": 0, "failed": 0, "skipped": 0,
        },
    )
    assert response.status_code == 401


def test_rejects_wrong_api_key():
    response = client.post(
        "/api/v1/ci/test-results",
        json={
            "repository": "r", "commit_sha": "c", "branch": "b",
            "total_tests": 0, "passed": 0, "failed": 0, "skipped": 0,
        },
        headers={"X-API-Key": "wrong"},
    )
    assert response.status_code == 401


def test_stores_test_results():
    response = _post_ci_result("acme/repo", "sha1", {"test_x": "passed"})
    assert response.status_code == 200
    assert "test_run_id" in response.json()


def test_flaky_test_detection():
    _post_ci_result("acme/repo", "sha1", {"test_x": "passed", "test_y": "passed"})
    _post_ci_result("acme/repo", "sha2", {"test_x": "failed", "test_y": "passed"})
    _post_ci_result("acme/repo", "sha3", {"test_x": "passed", "test_y": "passed"})

    response = client.get(
        "/api/v1/flaky-tests",
        params={"repository": "acme/repo", "branch": "main"},
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 200

    flaky = response.json()
    names = {t["test_name"] for t in flaky}

    assert "test_x" in names
    assert "test_y" not in names


def test_history_endpoint_orders_newest_first():
    _post_ci_result("acme/repo", "sha1", {"test_x": "passed"})
    _post_ci_result("acme/repo", "sha2", {"test_x": "failed"})

    response = client.get(
        "/api/v1/flaky-tests/test_x/history",
        params={"repository": "acme/repo"},
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 200

    history = response.json()
    assert len(history) == 2
    assert history[0]["outcome"] == "failed"


def test_explain_returns_501_without_ai_key():
    _post_ci_result("acme/repo", "sha1", {"test_x": "failed"})

    response = client.get(
        "/api/v1/flaky-tests/test_x/explain",
        params={"repository": "acme/repo"},
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 501


def test_flaky_tests_requires_api_key():
    response = client.get(
        "/api/v1/flaky-tests",
        params={"repository": "acme/repo"},
    )
    assert response.status_code == 401


def test_dashboard_requires_key():
    assert client.get("/dashboard").status_code == 401
    assert client.get("/dashboard", params={"key": "wrong"}).status_code == 401
    assert client.get("/dashboard", params={"key": API_KEY}).status_code == 200


def test_github_webhook_ping():
    body = b'{"zen": "hello"}'
    response = client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": _github_signature(body),
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"message": "pong"}


def test_github_webhook_rejects_bad_signature():
    body = b'{"zen": "hello"}'
    response = client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": "sha256=deadbeef",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 401
