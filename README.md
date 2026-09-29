# FlakeGuard

FlakeGuard detects flaky tests: tests whose outcome flips between passed
and failed across otherwise-unrelated CI runs. It ingests per-test results
from your CI pipeline, stores them, flags flip-flopping tests, and shows
them on a dashboard.

## Architecture

```
pytest --json-report  →  scripts/send_result.py  →  FastAPI  →  PostgreSQL
                                                        │
                                                        ├─ enqueues a job →  Redis  →  RQ worker
                                                        │                              (recomputes + caches
                                                        │                               flaky tests)
                                                        └─ /dashboard (Jinja2 + Chart.js)

GitHub  →  /api/v1/webhooks/github  (HMAC-verified workflow_run events)
```

- **backend/main.py** — FastAPI app: ingestion, flaky-tests API, dashboard,
  GitHub webhook, AI-explanation endpoint.
- **backend/models.py** — `TestRun` (one CI run) and `TestResult` (one
  test's outcome within a run).
- **backend/flaky_detector.py** — the detection engine: a test is flaky if,
  within its most recent `window` runs (default 20), it has at least
  `min_runs` (default 3) recorded outcomes and more than one distinct
  outcome (i.e. it has both passed and failed).
- **backend/tasks.py** / **backend/worker.py** — background recomputation
  of flaky tests per repository, cached in Redis for 5 minutes so the API
  and dashboard don't recompute on every request.
- **alembic/** — schema migrations.

## Local development

### Option A: Docker Compose (recommended)

```bash
cp .env.example .env   # if you keep one; otherwise export the vars below
docker compose up --build
```

This starts Postgres, Redis, the API (with migrations run automatically),
and the RQ worker. The API is on `http://localhost:8000`, dashboard at
`http://localhost:8000/dashboard?key=devkey` (the default `FLAKEGUARD_API_KEY`
in `docker-compose.yml`).

### Option B: run directly

```bash
python -m venv venvflake && source venvflake/bin/activate
pip install -r requirements.txt

export DATABASE_URL="postgresql+psycopg2://postgres:1234@localhost:5432/flakeguard"
export FLAKEGUARD_API_KEY="devkey"
export REDIS_URL="redis://localhost:6379/0"   # optional locally; API degrades gracefully without it

alembic upgrade head
uvicorn backend.main:app --reload

# in another terminal, to enable background caching:
python -m backend.worker
```

> **macOS note:** the RQ worker forks a subprocess per job. If it crashes
> with an `NSCharacterSet` / Objective-C fork-safety error, run it with
> `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES python -m backend.worker`. This
> is a macOS-only quirk and does not affect Linux/Docker.

## Environment variables

| Variable                | Required | Purpose                                                        |
|--------------------------|----------|-----------------------------------------------------------------|
| `DATABASE_URL`           | yes      | PostgreSQL connection string                                    |
| `FLAKEGUARD_API_KEY`     | yes      | Shared secret CI must send as `X-API-Key` to ingest results     |
| `REDIS_URL`              | no       | Enables background recomputation + caching (default `redis://localhost:6379/0`) |
| `GITHUB_WEBHOOK_SECRET`  | no       | Enables `/api/v1/webhooks/github` (HMAC signature verification) |
| `ANTHROPIC_API_KEY`      | no       | Enables the AI-explanation endpoint                              |

## API

All endpoints below except the webhook require `FLAKEGUARD_API_KEY`, since
they can expose repository names, commit SHAs, and raw error messages from
CI runs.

- `POST /api/v1/ci/test-results` — ingest a CI run (requires `X-API-Key`
  header). Body: `{repository, commit_sha, branch, total_tests, passed,
  failed, skipped, test_results: [{test_name, outcome, duration,
  error_message?}]}`.
- `GET /api/v1/flaky-tests?repository=&branch=` — list currently flaky
  tests (requires `X-API-Key` header).
- `GET /api/v1/flaky-tests/{test_name}/history?repository=` — recent
  outcome history for one test (requires `X-API-Key` header).
- `GET /api/v1/flaky-tests/{test_name}/explain?repository=` — AI-generated
  guess at the cause (requires `X-API-Key` header; 501 if
  `ANTHROPIC_API_KEY` isn't set).
- `GET /dashboard?repository=&key=` — HTML dashboard. Since it's opened
  directly in a browser, it's authenticated via a `?key=` query param
  (matching `FLAKEGUARD_API_KEY`) instead of a header.
- `POST /api/v1/webhooks/github` — GitHub webhook receiver (401 if the
  `X-Hub-Signature-256` doesn't match `GITHUB_WEBHOOK_SECRET`).

## Wiring up GitHub Actions

Already wired in `.github/workflows/tests.yml`: it runs pytest with
`--json-report`, then runs `scripts/send_result.py`, which reads the report
and POSTs the per-test results to FlakeGuard. Set these repo secrets:

- `FLAKEGUARD_API_URL` — your deployed FlakeGuard base URL
- `FLAKEGUARD_API_KEY` — must match the server's `FLAKEGUARD_API_KEY`

## Wiring up the GitHub webhook (optional)

In your repo's Settings → Webhooks, add a webhook pointing at
`https://<your-flakeguard-host>/api/v1/webhooks/github`, content type
`application/json`, a secret matching `GITHUB_WEBHOOK_SECRET`, subscribed
to "Workflow runs". FlakeGuard verifies the signature and currently
acknowledges `workflow_run` events (a starting point for richer
integration, e.g. posting flaky-test warnings as PR comments).

## Deployment (Render)

`render.yaml` defines three services: the web API, an RQ worker, and a
managed Redis instance. Set `DATABASE_URL`, `FLAKEGUARD_API_KEY`, and
optionally `GITHUB_WEBHOOK_SECRET`/`ANTHROPIC_API_KEY` in the Render
dashboard for the `flakeguard` (and `flakeguard-worker`, for `DATABASE_URL`)
services. `start.sh` runs `alembic upgrade head` before starting the API.

## Testing

```bash
python -m pytest test/ -v
```

`test/test_api.py` covers auth, ingestion, flaky detection, history,
the AI-explanation gate, and GitHub webhook signature verification, all
against an in-memory SQLite database (no Postgres/Redis required to run
the suite).
