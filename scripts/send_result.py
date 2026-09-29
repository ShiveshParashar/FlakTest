import json
import os
import sys
import time
from pathlib import Path

import requests


REPORT_FILE = Path(
    os.getenv("TEST_REPORT_FILE", "test-report.json")
)

API_URL = os.getenv("FLAKEGUARD_API_URL")
API_KEY = os.getenv("FLAKEGUARD_API_KEY")


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


def get_summary(report):
    summary = report.get("summary", {})

    return {
        "total_tests": summary.get("total", 0),
        "passed": summary.get("passed", 0),
        "failed": summary.get("failed", 0),
        "skipped": summary.get("skipped", 0),
    }


def get_test_results(report):
    test_results = []

    for test in report.get("tests", []):
        call = test.get("call", test.get("setup", {}))

        error_message = call.get("longrepr")

        test_results.append({
            "test_name": test.get("nodeid", "unknown"),
            "outcome": test.get("outcome", "unknown"),
            "duration": call.get("duration", 0.0),
            "error_message": str(error_message) if error_message else None,
        })

    return test_results


def build_payload(report):
    summary = get_summary(report)

    return {
        "repository": os.getenv(
            "GITHUB_REPOSITORY",
            "unknown"
        ),
        "commit_sha": os.getenv(
            "GITHUB_SHA",
            "unknown"
        ),
        "branch": os.getenv(
            "GITHUB_REF_NAME",
            "unknown"
        ),
        "total_tests": summary["total_tests"],
        "passed": summary["passed"],
        "failed": summary["failed"],
        "skipped": summary["skipped"],
        "test_results": get_test_results(report),
    }


def send_results(payload):
    if not API_URL:
        print("ERROR: FLAKEGUARD_API_URL is not set.")
        sys.exit(1)

    if not API_KEY:
        print("ERROR: FLAKEGUARD_API_KEY is not set.")
        sys.exit(1)

    url = API_URL.rstrip("/") + "/api/v1/ci/test-results"

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
    }

    print(f"Sending results to: {url}")

    attempts = 3
    response = None

    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                # Generous timeout: free-tier hosts (e.g. Render) can take
                # 30-60s to wake up from an idle spin-down on the first hit.
                timeout=60,
            )
            break
        except requests.RequestException as exc:
            print(f"Attempt {attempt}/{attempts} failed: {exc}")

            if attempt == attempts:
                print("ERROR: Could not connect to FlakeGuard API.")
                sys.exit(1)

            time.sleep(10)

    print(f"FlakeGuard API status: {response.status_code}")

    if response.text:
        print(f"FlakeGuard response: {response.text}")

    if not response.ok:
        print("ERROR: FlakeGuard API rejected the test results.")
        sys.exit(1)

    print("Test results successfully sent to FlakeGuard.")


def main():
    print(f"Reading test report: {REPORT_FILE}")

    report = load_report()

    payload = build_payload(report)

    print("\nPayload:")
    print(json.dumps(payload, indent=2))

    send_results(payload)


if __name__ == "__main__":
    main()