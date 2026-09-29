import hashlib
import hmac
import json

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import ai_explain
from .config import FLAKEGUARD_API_KEY, GITHUB_WEBHOOK_SECRET
from .database import get_db
from .flaky_detector import get_flaky_tests as compute_flaky_tests
from .flaky_detector import get_test_history
from .models import TestResult as TestResultModel
from .models import TestRun as TestRunModel
from .redis_client import get_redis, task_queue
from .tasks import flaky_tests_cache_key, recompute_flaky_tests


app = FastAPI(
    title="FlakeGuard API",
    description="API for detecting and analyzing flaky tests",
    version="0.1.0",
)

templates = Jinja2Templates(directory="backend/templates")


class TestResultIn(BaseModel):
    test_name: str
    outcome: str
    duration: float
    error_message: str | None = None


class CIResult(BaseModel):
    repository: str
    commit_sha: str
    branch: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    test_results: list[TestResultIn] = []


def verify_api_key(
    x_api_key: str = Header(default=None),
):
    if not x_api_key or x_api_key != FLAKEGUARD_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )


def verify_dashboard_key(key: str | None = None):
    """Browser-friendly auth for /dashboard: a query param instead of a
    header, since it's meant to be opened directly in a browser."""
    if not key or key != FLAKEGUARD_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid ?key=",
        )


def verify_github_signature(body: bytes, signature_header: str | None) -> bool:
    if not GITHUB_WEBHOOK_SECRET:
        return False

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    provided = signature_header.removeprefix("sha256=")

    return hmac.compare_digest(expected, provided)


@app.get("/")
def root():
    return {
        "message": "FlakeGuard API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.post("/api/v1/ci/test-results")
def receive_ci_results(
    result: CIResult,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    test_run = TestRunModel(
        repository=result.repository,
        commit_sha=result.commit_sha,
        branch=result.branch,
        total_tests=result.total_tests,
        passed=result.passed,
        failed=result.failed,
        skipped=result.skipped,
    )

    db.add(test_run)
    db.flush()

    for test_result in result.test_results:
        db.add(
            TestResultModel(
                test_run_id=test_run.id,
                test_name=test_result.test_name,
                outcome=test_result.outcome,
                duration=test_result.duration,
                error_message=test_result.error_message,
            )
        )

    db.commit()
    db.refresh(test_run)

    try:
        task_queue.enqueue(recompute_flaky_tests, result.repository)
    except Exception:
        pass

    return {
        "message": "CI test results received",
        "test_run_id": test_run.id,
    }


@app.get("/api/v1/flaky-tests")
def get_flaky_tests(
    repository: str | None = None,
    branch: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    if repository and not branch:
        redis_conn = get_redis()

        if redis_conn is not None:
            cached = redis_conn.get(flaky_tests_cache_key(repository))

            if cached is not None:
                return json.loads(cached)

    return compute_flaky_tests(db, repository=repository, branch=branch)


@app.get("/api/v1/flaky-tests/{test_name:path}/history")
def get_flaky_test_history(
    test_name: str,
    repository: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    return get_test_history(db, test_name=test_name, repository=repository)


@app.get("/api/v1/flaky-tests/{test_name:path}/explain")
def explain_flaky_test(
    test_name: str,
    repository: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    if not ai_explain.is_configured():
        raise HTTPException(
            status_code=501,
            detail=(
                "AI explanations are not configured. "
                "Set ANTHROPIC_API_KEY to enable this feature."
            ),
        )

    history = get_test_history(db, test_name=test_name, repository=repository)

    if not history:
        raise HTTPException(status_code=404, detail="No history for this test")

    explanation = ai_explain.explain_flaky_test(test_name, history)

    return {"test_name": test_name, "explanation": explanation}


@app.post("/api/v1/webhooks/github")
async def github_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not verify_github_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event = request.headers.get("X-GitHub-Event", "unknown")
    payload = await request.json()

    if event == "ping":
        return {"message": "pong"}

    if event == "workflow_run":
        workflow_run = payload.get("workflow_run", {})

        return {
            "message": "workflow_run event received",
            "repository": payload.get("repository", {}).get("full_name"),
            "workflow": workflow_run.get("name"),
            "conclusion": workflow_run.get("conclusion"),
            "branch": workflow_run.get("head_branch"),
            "commit_sha": workflow_run.get("head_sha"),
        }

    return {"message": f"event '{event}' ignored"}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    repository: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(verify_dashboard_key),
):
    flaky_tests = compute_flaky_tests(db, repository=repository)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "repository": repository,
            "flaky_tests": flaky_tests,
            "labels": [t["test_name"] for t in flaky_tests],
            "rates": [round(t["flake_rate"] * 100, 1) for t in flaky_tests],
        },
    )
