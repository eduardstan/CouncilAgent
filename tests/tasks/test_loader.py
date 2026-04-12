"""Tests for tasks/loader.py, tasks/gsm8k.py, tasks/registry.py."""

from __future__ import annotations

import pytest

from tasks.loader import BenchmarkTask, TaskLoader
from tasks.registry import REGISTRY


# ---------------------------------------------------------------------------
# BenchmarkTask contract
# ---------------------------------------------------------------------------


def test_benchmark_task_is_frozen() -> None:
    t = BenchmarkTask(id="x", question="q", ground_truth="a", domain="math")
    with pytest.raises((AttributeError, TypeError)):
        t.id = "y"  # type: ignore[misc]


def test_benchmark_task_optional_difficulty() -> None:
    t = BenchmarkTask(id="x", question="q", ground_truth="a", domain="math")
    assert t.difficulty is None


# ---------------------------------------------------------------------------
# TaskLoader contract — fake loader
# ---------------------------------------------------------------------------


class _FixtureLoader(TaskLoader):
    """Deterministic in-memory loader for contract tests."""

    _TASKS = [
        BenchmarkTask(id=f"test-{i}", question=f"Q{i}?", ground_truth=str(i), domain="test")
        for i in range(5)
    ]

    @property
    def name(self) -> str:
        return "fixture"

    def load(self, limit: int | None = None) -> list[BenchmarkTask]:
        return self._TASKS[:limit] if limit is not None else list(self._TASKS)


def test_loader_returns_all_tasks_when_no_limit() -> None:
    loader = _FixtureLoader()
    assert len(loader.load()) == 5


def test_loader_respects_limit() -> None:
    loader = _FixtureLoader()
    assert len(loader.load(limit=3)) == 3


def test_loader_limit_zero_returns_empty() -> None:
    loader = _FixtureLoader()
    assert loader.load(limit=0) == []


def test_loader_limit_larger_than_dataset_returns_all() -> None:
    loader = _FixtureLoader()
    assert len(loader.load(limit=100)) == 5


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_contains_gsm8k() -> None:
    assert "gsm8k" in REGISTRY


def test_registry_value_is_task_loader() -> None:
    assert isinstance(REGISTRY["gsm8k"], TaskLoader)


def test_registry_gsm8k_name() -> None:
    assert REGISTRY["gsm8k"].name == "gsm8k"


# ---------------------------------------------------------------------------
# GSM8K answer extraction (unit — no network call)
# ---------------------------------------------------------------------------


def test_gsm8k_answer_extraction() -> None:
    from tasks.gsm8k import _extract_answer

    assert _extract_answer("He had 5 apples.\n#### 5") == "5"


def test_gsm8k_answer_extraction_with_comma() -> None:
    from tasks.gsm8k import _extract_answer

    assert _extract_answer("Total: #### 1,234") == "1234"


def test_gsm8k_answer_extraction_fallback() -> None:
    from tasks.gsm8k import _extract_answer

    assert _extract_answer("no delimiter here") == "no delimiter here"


# ---------------------------------------------------------------------------
# GSM8K loader — real network call, gated
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_gsm8k_loader_returns_benchmark_tasks() -> None:
    pytest.importorskip("datasets", reason="requires benchmark extras: uv pip install 'council-agent[benchmark]'")
    from tasks.gsm8k import GSM8KLoader

    loader = GSM8KLoader()
    tasks = loader.load(limit=5)
    assert len(tasks) == 5
    for t in tasks:
        assert isinstance(t, BenchmarkTask)
        assert t.domain == "math"
        assert t.ground_truth != ""
        assert t.id.startswith("gsm8k-test-")


@pytest.mark.integration
def test_gsm8k_loader_limit() -> None:
    pytest.importorskip("datasets", reason="requires benchmark extras: uv pip install 'council-agent[benchmark]'")
    from tasks.gsm8k import GSM8KLoader

    assert len(GSM8KLoader().load(limit=3)) == 3
