import os

FLAKEGUARD_API_KEY = os.getenv(
    "FLAKEGUARD_API_KEY",
    "development-secret",
)
