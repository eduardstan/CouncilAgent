"""Tests for experiments/run.py — config loading, ExperimentSummary contract, factories.

Pipeline end-to-end experiments are integration tests gated by RUN_INTEGRATION=1.
These unit tests cover the infrastructure layer only.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from experiments.run import (
    ExperimentSummary,
    _build_aggregation,
    _build_termination,
    _build_topology,
    load_config,
)


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


# ---------------------------------------------------------------------------
# Task 6.1 — factory functions for topology, aggregation, termination
# ---------------------------------------------------------------------------


class TestBuildTopology:
    def test_complete(self) -> None:
        from council.topology import CompleteGraphTopology
        t = _build_topology("complete", 3)
        assert isinstance(t, CompleteGraphTopology)

    def test_star(self) -> None:
        from council.topology import StarTopology
        t = _build_topology("star", 3)
        assert isinstance(t, StarTopology)

    def test_bus(self) -> None:
        from council.topology import BusTopology
        t = _build_topology("bus", 3)
        assert isinstance(t, BusTopology)

    def test_ring(self) -> None:
        from council.topology import RingTopology
        t = _build_topology("ring", 4)
        assert isinstance(t, RingTopology)

    def test_dynamic_star(self) -> None:
        from council.topology import DynamicStarTopology
        t = _build_topology("dynamic_star", 4)
        assert isinstance(t, DynamicStarTopology)

    def test_unknown_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown topology"):
            _build_topology("unknown_topology", 3)

    def test_num_agents_passed_through(self) -> None:
        t = _build_topology("complete", 5)
        assert t.num_agents == 5


class TestBuildAggregation:
    def _normalizer(self):  # type: ignore[no-untyped-def]
        from council.normalizer import IdentityNormalizer
        return IdentityNormalizer()

    def test_majority_vote(self) -> None:
        from council.aggregation import MajorityVote
        agg = _build_aggregation("majority_vote", self._normalizer(), None, [])
        assert isinstance(agg, MajorityVote)

    def test_borda(self) -> None:
        from council.aggregation import BordaCount
        agg = _build_aggregation("borda", self._normalizer(), None, [])
        assert isinstance(agg, BordaCount)

    def test_condorcet(self) -> None:
        from council.aggregation import CondorcetAggregation
        agg = _build_aggregation("condorcet", self._normalizer(), None, [])
        assert isinstance(agg, CondorcetAggregation)

    def test_unknown_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown aggregation"):
            _build_aggregation("unknown_agg", self._normalizer(), None, [])


class TestBuildTermination:
    def _normalizer(self):  # type: ignore[no-untyped-def]
        from council.normalizer import IdentityNormalizer
        return IdentityNormalizer()

    def test_fixed(self) -> None:
        from council.termination import FixedRounds
        t = _build_termination("fixed", total_rounds=3, normalizer=self._normalizer(), budget_usd=1.0)
        assert isinstance(t, FixedRounds)

    def test_agreement(self) -> None:
        from council.termination import CompositeTermination
        t = _build_termination("agreement", total_rounds=3, normalizer=self._normalizer(), budget_usd=1.0)
        assert isinstance(t, CompositeTermination)

    def test_budget(self) -> None:
        from council.termination import BudgetExhaustion
        t = _build_termination("budget", total_rounds=3, normalizer=self._normalizer(), budget_usd=1.0)
        assert isinstance(t, BudgetExhaustion)

    def test_composite(self) -> None:
        from council.termination import CompositeTermination
        t = _build_termination("composite", total_rounds=3, normalizer=self._normalizer(), budget_usd=1.0)
        assert isinstance(t, CompositeTermination)

    def test_unknown_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown termination"):
            _build_termination("unknown_term", total_rounds=3, normalizer=self._normalizer(), budget_usd=1.0)


class TestYamlConfigsHaveNewKeys:
    def test_fast_config_has_topology(self) -> None:
        cfg = load_config("configs/experiment/fast.yaml")
        assert cfg["council"]["topology"] == "complete"

    def test_fast_config_has_aggregation(self) -> None:
        cfg = load_config("configs/experiment/fast.yaml")
        assert cfg["council"]["aggregation"] == "majority_vote"

    def test_fast_config_has_termination(self) -> None:
        cfg = load_config("configs/experiment/fast.yaml")
        assert cfg["council"]["termination"] == "fixed"

    def test_full_config_has_topology(self) -> None:
        cfg = load_config("configs/experiment/full.yaml")
        assert cfg["council"]["topology"] == "complete"
