import json
import os
import sys

import requests


API_URL = os.environ["FLAKEGUARD_API_URL"]
API_KEY = os.environ["FLAKEGUARD_API_KEY"]

REPORT_FILE = "test-report.json"


with open(REPORT_FILE, "r", encoding="utf-8") as file:
    report = json.load(file)


summary = report["summary"]

payload = {
    "repository": os.environ["GITHUB_REPOSITORY"],
    "commit_sha": os.environ["GITHUB_SHA"],
    "branch": os.environ.get("GITHUB_REF_NAME", "unknown"),
    "total_tests": summary["total"],
    "passed": summary["passed"],
    "failed": summary["failed"],
    "skipped": summary["skipped"],
}


response = requests.post(
    f"{API_URL}/api/v1/ci/test-results",
    json=payload,
    headers={
        "X-API-Key": API_KEY,
    },
    timeout=30,
)


if response.status_code >= 400:
    print(response.text)
    sys.exit(1)


print("FlakeGuard response:")
print(response.json())