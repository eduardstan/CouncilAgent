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
              models:
                - fake/model-a
                - fake/model-b
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

    def test_meta_judge_uses_explicit_model_when_set(self) -> None:
        from council.aggregation import MetaJudge
        from council.models import FakeModelClient
        client = FakeModelClient({})
        agg = _build_aggregation(
            "meta_judge", self._normalizer(), client,
            models=["fallback/model"],
            meta_judge_model="explicit/judge-model",
        )
        assert isinstance(agg, MetaJudge)
        assert agg._model == "explicit/judge-model"  # type: ignore[attr-defined]

    def test_meta_judge_falls_back_to_models_0_when_no_explicit(self) -> None:
        from council.aggregation import MetaJudge
        from council.models import FakeModelClient
        client = FakeModelClient({})
        agg = _build_aggregation(
            "meta_judge", self._normalizer(), client,
            models=["primary/model", "secondary/model"],
        )
        assert isinstance(agg, MetaJudge)
        assert agg._model == "primary/model"  # type: ignore[attr-defined]


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


class TestMissingModelsRaises:
    async def test_run_experiment_raises_when_models_absent(self, tmp_path: Path) -> None:
        """council.models is now required; omitting it must raise ValueError, not silently
        fall back to hardcoded model strings."""
        cfg = {
            "name": "no_models",
            "dataset": "gsm8k",
            "task_limit": 1,
            "council": {
                "protocol": "direct",
                "max_rounds": 0,
                # "models" key intentionally absent
            },
        }
        from experiments.run import run_experiment
        with pytest.raises(ValueError, match="council.models must be specified"):
            await run_experiment(cfg)


class TestTaskProfileDrivenRunner:
    def test_registry_exposes_gsm8k_profile(self) -> None:
        from tasks.profiles import get_profile
        p = get_profile("gsm8k")
        assert p.name == "gsm8k"
        assert p.output_schema is not None
        assert p.prompt_hint  # non-empty

    def test_unknown_dataset_raises(self) -> None:
        from tasks.profiles import get_profile
        with pytest.raises(ValueError, match="Unknown dataset"):
            get_profile("nonexistent_dataset")

    @pytest.mark.filterwarnings("ignore::FutureWarning")
    async def test_config_prompt_hint_overrides_profile(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """When council.prompt_hint is set in YAML, it wins over the profile default."""
        import council.core
        import experiments.run as runmod
        from tasks.loader import BenchmarkTask, TaskLoader
        from tasks.registry import REGISTRY

        captured: dict[str, object] = {}

        class _StubResult:
            final_answer = "42"
            confidence = 1.0
            total_cost = 0.0
            rounds_used = 1
            tokens_in = 0
            tokens_out = 0
            round_history: list[object] = []

        async def fake_run_council(**kwargs):  # type: ignore[no-untyped-def]
            captured.update(kwargs)
            return _StubResult()

        class _StubLoader(TaskLoader):
            def load(self, limit=None):  # type: ignore[override, no-untyped-def]
                return [BenchmarkTask(id="t1", question="Q?", ground_truth="42", domain="math")]

            @property
            def name(self) -> str:
                return "gsm8k"

        monkeypatch.setattr(council.core, "run_council", fake_run_council)
        monkeypatch.setitem(REGISTRY, "gsm8k", _StubLoader())

        cfg = {
            "name": "hint_override",
            "dataset": "gsm8k",
            "task_limit": 1,
            "council": {
                "models": ["fake/a", "fake/b"],
                "max_rounds": 0,
                "protocol": "direct",
                "aggregation": "majority_vote",
                "termination": "fixed",
                "task_delay_seconds": 0,
                "prompt_hint": "CUSTOM OVERRIDE HINT",
            },
        }
        await runmod.run_experiment(cfg)
        assert captured.get("task_hint") == "CUSTOM OVERRIDE HINT"

    @pytest.mark.filterwarnings("ignore::FutureWarning")
    async def test_profile_prompt_hint_used_when_config_absent(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Without config override, the TaskProfile's prompt_hint is used."""
        import council.core
        import experiments.run as runmod
        from tasks.loader import BenchmarkTask, TaskLoader
        from tasks.profiles import get_profile
        from tasks.registry import REGISTRY

        captured: dict[str, object] = {}

        class _StubResult:
            final_answer = "42"
            confidence = 1.0
            total_cost = 0.0
            rounds_used = 1
            tokens_in = 0
            tokens_out = 0
            round_history: list[object] = []

        async def fake_run_council(**kwargs):  # type: ignore[no-untyped-def]
            captured.update(kwargs)
            return _StubResult()

        class _StubLoader(TaskLoader):
            def load(self, limit=None):  # type: ignore[override, no-untyped-def]
                return [BenchmarkTask(id="t1", question="Q?", ground_truth="42", domain="math")]

            @property
            def name(self) -> str:
                return "gsm8k"

        monkeypatch.setattr(council.core, "run_council", fake_run_council)
        monkeypatch.setitem(REGISTRY, "gsm8k", _StubLoader())

        cfg = {
            "name": "profile_default",
            "dataset": "gsm8k",
            "task_limit": 1,
            "council": {
                "models": ["fake/a", "fake/b"],
                "max_rounds": 0,
                "protocol": "direct",
                "aggregation": "majority_vote",
                "termination": "fixed",
                "task_delay_seconds": 0,
            },
        }
        await runmod.run_experiment(cfg)
        assert captured.get("task_hint") == get_profile("gsm8k").prompt_hint


class TestYamlConfigsHaveNewKeys:
    def test_fast_config_has_topology(self) -> None:
        cfg = load_config("configs/experiment/fast.yaml")
        assert cfg["council"]["topology"] == "complete"

    def test_fast_config_has_aggregation(self) -> None:
        cfg = load_config("configs/experiment/fast.yaml")
        # fast.yaml uses meta_judge: the integration baseline exercises the
        # full informed-aggregation path (debate transcript + synthesis).
        assert cfg["council"]["aggregation"] == "meta_judge"

    def test_fast_config_has_termination(self) -> None:
        cfg = load_config("configs/experiment/fast.yaml")
        assert cfg["council"]["termination"] == "fixed"

    def test_full_config_has_topology(self) -> None:
        cfg = load_config("configs/experiment/full.yaml")
        assert cfg["council"]["topology"] == "complete"
