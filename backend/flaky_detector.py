from sqlalchemy import case, func
from sqlalchemy.orm import Session

from .models import TestResult, TestRun


DEFAULT_WINDOW = 20
DEFAULT_MIN_RUNS = 3


def get_flaky_tests(
    db: Session,
    repository: str | None = None,
    branch: str | None = None,
    window: int = DEFAULT_WINDOW,
    min_runs: int = DEFAULT_MIN_RUNS,
):
    """Detect flaky tests: tests whose outcome flips within their
    most recent `window` runs, seen at least `min_runs` times."""

    row_number = (
        func.row_number()
        .over(
            partition_by=[TestRun.repository, TestResult.test_name],
            order_by=TestRun.created_at.desc(),
        )
        .label("rn")
    )

    recent_runs = (
        db.query(
            TestRun.repository.label("repository"),
            TestResult.test_name.label("test_name"),
            TestResult.outcome.label("outcome"),
            TestRun.created_at.label("created_at"),
            row_number,
        )
        .join(TestRun, TestResult.test_run_id == TestRun.id)
    )

    if repository:
        recent_runs = recent_runs.filter(TestRun.repository == repository)
    if branch:
        recent_runs = recent_runs.filter(TestRun.branch == branch)

    recent_runs = recent_runs.subquery()

    query = (
        db.query(
            recent_runs.c.repository,
            recent_runs.c.test_name,
            func.count(recent_runs.c.outcome).label("total_runs"),
            func.sum(
                case((recent_runs.c.outcome == "passed", 1), else_=0)
            ).label("passed_count"),
            func.sum(
                case((recent_runs.c.outcome == "failed", 1), else_=0)
            ).label("failed_count"),
            func.max(recent_runs.c.created_at).label("last_seen"),
        )
        .filter(recent_runs.c.rn <= window)
        .group_by(recent_runs.c.repository, recent_runs.c.test_name)
        .having(func.count(func.distinct(recent_runs.c.outcome)) > 1)
        .having(func.count(recent_runs.c.outcome) >= min_runs)
    )

    results = []

    for row in query.all():
        flake_rate = min(row.passed_count, row.failed_count) / row.total_runs

        results.append({
            "repository": row.repository,
            "test_name": row.test_name,
            "total_runs": row.total_runs,
            "passed": row.passed_count,
            "failed": row.failed_count,
            "flake_rate": round(flake_rate, 3),
            "last_seen": row.last_seen,
        })

    results.sort(key=lambda item: item["flake_rate"], reverse=True)

    return results


def get_test_history(
    db: Session,
    test_name: str,
    repository: str | None = None,
    limit: int = 50,
):
    """Return the most recent outcomes for a single test, newest first."""

    query = (
        db.query(
            TestRun.commit_sha.label("commit_sha"),
            TestRun.branch.label("branch"),
            TestRun.created_at.label("created_at"),
            TestResult.outcome.label("outcome"),
            TestResult.duration.label("duration"),
            TestResult.error_message.label("error_message"),
        )
        .join(TestRun, TestResult.test_run_id == TestRun.id)
        .filter(TestResult.test_name == test_name)
    )

    if repository:
        query = query.filter(TestRun.repository == repository)

    query = query.order_by(TestRun.created_at.desc()).limit(limit)

    return [
        {
            "commit_sha": row.commit_sha,
            "branch": row.branch,
            "created_at": row.created_at,
            "outcome": row.outcome,
            "duration": row.duration,
            "error_message": row.error_message,
        }
        for row in query.all()
    ]
