"""Tests for experiments/run.py — config loading, ExperimentSummary contract.

Pipeline end-to-end experiments are integration tests gated by RUN_INTEGRATION=1.
These unit tests cover the infrastructure layer only.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from experiments.run import ExperimentSummary, load_config


# ---------------------------------------------------------------------------
# ExperimentSummary
# ---------------------------------------------------------------------------


class TestExperimentSummary:
    def test_default_fields(self) -> None:
        s = ExperimentSummary(
            config_name="test",
            task_count=5,
            mean_accuracy=0.8,
            mean_cost=0.0,
        )
        assert s.baseline_comparison == {}
        assert s.mlflow_run_id == ""
        assert s.errors == []

    def test_baseline_comparison_stored(self) -> None:
        s = ExperimentSummary(
            config_name="x",
            task_count=10,
            mean_accuracy=0.9,
            mean_cost=0.0,
            baseline_comparison={"majority_vote": 0.7},
        )
        assert s.baseline_comparison["majority_vote"] == pytest.approx(0.7)

    def test_errors_list(self) -> None:
        s = ExperimentSummary(
            config_name="x",
            task_count=5,
            mean_accuracy=0.5,
            mean_cost=0.0,
            errors=["task-1: timeout"],
        )
        assert len(s.errors) == 1


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_loads_yaml_file(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "test.yaml"
        cfg_file.write_text(textwrap.dedent("""
            name: unit_test
            dataset: gsm8k
            task_limit: 5
            council:
              max_rounds: 1
        """))
        cfg = load_config(cfg_file)
        assert cfg["name"] == "unit_test"
        assert cfg["dataset"] == "gsm8k"
        assert cfg["task_limit"] == 5

    def test_fast_config_valid(self) -> None:
        cfg = load_config("configs/experiment/fast.yaml")
        assert cfg["name"] == "fast"
        assert cfg["dataset"] == "gsm8k"
        assert cfg["task_limit"] == 3
        assert cfg["council"]["max_rounds"] == 1

    def test_full_config_valid(self) -> None:
        cfg = load_config("configs/experiment/full.yaml")
        assert cfg["name"] == "full"
        assert cfg["task_limit"] is None  # full split

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_config("configs/experiment/nonexistent.yaml")


# ---------------------------------------------------------------------------
# _git_sha (smoke — just checks it returns a string)
# ---------------------------------------------------------------------------


def test_git_sha_returns_string() -> None:
    from experiments.run import _git_sha
    sha = _git_sha()
    assert isinstance(sha, str)
    assert len(sha) > 0
