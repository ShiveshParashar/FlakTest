import json
import os
import sys
from pathlib import Path

import requests


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

REPORT_FILE = Path(
    os.getenv("TEST_REPORT_FILE", "test-report.json")
)

API_URL = os.getenv("FLAKEGUARD_API_URL")
API_SECRET = os.getenv("FLAKEGUARD_API_SECRET")


# ---------------------------------------------------------
# Read test report
# ---------------------------------------------------------

def load_report():
    if not REPORT_FILE.exists():
        print(f"ERROR: Test report not found: {REPORT_FILE}")
        sys.exit(1)

    try:
        with open(REPORT_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON report: {exc}")
        sys.exit(1)


# ---------------------------------------------------------
# Extract test summary
# ---------------------------------------------------------

def get_summary(report):
    summary = report.get("summary", {})

    # pytest-json-report normally provides these fields.
    # .get() prevents KeyError when a field is missing.
    return {
        "total": summary.get("total", 0),
        "passed": summary.get("passed", 0),
        "failed": summary.get("failed", 0),
        "skipped": summary.get("skipped", 0),
        "error": summary.get("error", 0),
        "xfailed": summary.get("xfailed", 0),
        "xpassed": summary.get("xpassed", 0),
    }


# ---------------------------------------------------------
# Build payload
# ---------------------------------------------------------

def build_payload(report):
    summary = get_summary(report)

    payload = {
        "summary": summary,
        "tests": report.get("tests", []),
        "created": report.get("created"),
        "duration": report.get("duration"),
    }

    # Useful GitHub Actions information
    github_payload = {
        "repository": os.getenv("GITHUB_REPOSITORY"),
        "commit_sha": os.getenv("GITHUB_SHA"),
        "branch": os.getenv("GITHUB_REF_NAME"),
        "run_id": os.getenv("GITHUB_RUN_ID"),
        "workflow": os.getenv("GITHUB_WORKFLOW"),
    }

    payload["github"] = github_payload

    return payload


# ---------------------------------------------------------
# Send results to FlakeGuard
# ---------------------------------------------------------

def send_results(payload):
    if not API_URL:
        print("ERROR: FLAKEGUARD_API_URL is not set.")
        sys.exit(1)

    if not API_SECRET:
        print("ERROR: FLAKEGUARD_API_SECRET is not set.")
        sys.exit(1)

    # Make sure we don't accidentally create:
    # https://example.com/api/results/api/results
    url = API_URL.rstrip("/") + "/api/results"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_SECRET}",
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30,
        )

    except requests.RequestException as exc:
        print(f"ERROR: Could not connect to FlakeGuard API: {exc}")
        sys.exit(1)

    print(f"FlakeGuard API status: {response.status_code}")

    if response.text:
        print(f"FlakeGuard response: {response.text}")

    if not response.ok:
        print("ERROR: FlakeGuard API rejected the test results.")
        sys.exit(1)

    print("Test results successfully sent to FlakeGuard.")


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():
    print(f"Reading test report: {REPORT_FILE}")

    report = load_report()

    summary = get_summary(report)

    print("\nTest Summary")
    print("-------------------------")
    print(f"Total:   {summary['total']}")
    print(f"Passed:  {summary['passed']}")
    print(f"Failed:  {summary['failed']}")
    print(f"Skipped: {summary['skipped']}")
    print(f"Errors:  {summary['error']}")
    print("-------------------------")

    payload = build_payload(report)

    send_results(payload)


if __name__ == "__main__":
    main()