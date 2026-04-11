"""Integration test gate. Real model calls are only allowed when RUN_INTEGRATION=1.

Any test under tests/integration/ is skipped unless the env var is set. Tests in
this directory should also carry `@pytest.mark.integration` for filtering.
"""

import os

import pytest

if os.environ.get("RUN_INTEGRATION") != "1":
    collect_ignore_glob = ["test_*.py"]


@pytest.fixture(scope="session")
def integration_enabled() -> bool:
    return os.environ.get("RUN_INTEGRATION") == "1"
