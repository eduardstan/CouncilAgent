"""Root conftest: shared fixtures and markers for the W0 test suite.

FakeModelClient is defined here once models.py exists (PR8).
At PR1 this file only registers markers and seeds randomness.
"""

from __future__ import annotations

import random

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: real model calls — gated by RUN_INTEGRATION=1 env var",
    )


@pytest.fixture(autouse=True)
def _seed_random() -> None:
    random.seed(0)
