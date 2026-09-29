from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import Depends, FastAPI, Header, HTTPException

from .config import FLAKEGUARD_API_KEY
from .database import get_db
from .models import TestRun as TestRunModel


app = FastAPI(
    title="FlakeGuard API",
    description="API for detecting and analyzing flaky tests",
    version="0.1.0",
)


class CIResult(BaseModel):
    repository: str
    commit_sha: str
    branch: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
FLAKEGUARD_API_KEY = "your-secret-key"


def verify_api_key(
    x_api_key: str = Header(default=None),
):
    if x_api_key != FLAKEGUARD_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )


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
    return {
        "message": "CI result received",
        "status": "success"
    }
@app.post("/api/v1/ci/test-results")
def receive_ci_results(
    result: CIResult,
    db: Session = Depends(get_db),
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
    db.commit()
    db.refresh(test_run)

    return {
        "message": "CI test results received",
        "test_run_id": test_run.id,
    }
