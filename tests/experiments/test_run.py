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
    _build_ranking,
    _build_termination,
    _build_topology,
    _parse_agents,
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
            meta_judge={"model": "explicit/judge-model"},
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

    def test_meta_judge_threads_overrides_from_dict(self) -> None:
        """YAML `meta_judge:` dict overrides flow to MetaJudge: model, temp, max_tokens, system_prompt."""
        from council.aggregation import MetaJudge
        from council.models import FakeModelClient
        client = FakeModelClient({})
        agg = _build_aggregation(
            "meta_judge", self._normalizer(), client,
            models=["fallback/model"],
            meta_judge={
                "model": "explicit/judge-model",
                "temperature": 0.05,
                "max_tokens": 4096,
                "system_prompt": "You are the final arbiter.",
            },
        )
        assert isinstance(agg, MetaJudge)
        assert agg._model == "explicit/judge-model"  # type: ignore[attr-defined]
        assert agg._temperature == 0.05  # type: ignore[attr-defined]
        assert agg._max_tokens == 4096  # type: ignore[attr-defined]
        assert agg._system_prompt == "You are the final arbiter."  # type: ignore[attr-defined]

    def test_meta_judge_empty_dict_uses_defaults(self) -> None:
        """Empty meta_judge dict falls back to models[0] and MetaJudge defaults."""
        from council.aggregation import MetaJudge
        from council.models import FakeModelClient
        client = FakeModelClient({})
        agg = _build_aggregation(
            "meta_judge", self._normalizer(), client,
            models=["primary/model"],
            meta_judge={},
        )
        assert isinstance(agg, MetaJudge)
        assert agg._model == "primary/model"  # type: ignore[attr-defined]
        assert agg._system_prompt is None  # type: ignore[attr-defined]


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

    def test_dict_form_agreement_threshold_overrides_default(self) -> None:
        """Audit §4 regression: dict form must inject agreement_threshold, not hardcode 0.8."""
        from council.termination import AgreementThreshold, CompositeTermination
        t = _build_termination(
            {"name": "agreement", "agreement_threshold": 0.95},
            total_rounds=3, normalizer=self._normalizer(), budget_usd=1.0,
        )
        assert isinstance(t, CompositeTermination)
        # Dig out the AgreementThreshold sub-strategy and verify the threshold.
        agreement_strat = next(
            s for s in t._strategies if isinstance(s, AgreementThreshold)
        )
        assert agreement_strat._threshold == pytest.approx(0.95)

    def test_bare_string_still_accepted(self) -> None:
        """Backward compat: bare string form still works after the dict-parser refactor."""
        from council.termination import FixedRounds
        t = _build_termination("fixed", total_rounds=5, normalizer=self._normalizer(), budget_usd=1.0)
        assert isinstance(t, FixedRounds)


class TestBuildRanking:
    def test_null_returns_null_ranking(self) -> None:
        from council.ranking import NullRanking
        assert isinstance(_build_ranking("null"), NullRanking)

    def test_regex_returns_regex_ordinal_ranking(self) -> None:
        from council.ranking import RegexOrdinalRanking
        assert isinstance(_build_ranking("regex"), RegexOrdinalRanking)

    def test_structured_returns_structured_ranking(self) -> None:
        from council.ranking import StructuredRanking
        assert isinstance(_build_ranking("structured"), StructuredRanking)

    def test_dict_form_accepted(self) -> None:
        from council.ranking import StructuredRanking
        assert isinstance(_build_ranking({"name": "structured"}), StructuredRanking)

    def test_default_bare_string_is_null(self) -> None:
        """Audit §1 regression: omitting ranking from YAML defaults to NullRanking."""
        from council.ranking import NullRanking
        assert isinstance(_build_ranking("null"), NullRanking)

    def test_unknown_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown ranking"):
            _build_ranking("magic_ranking")


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


class TestParseAgents:
    def test_bare_string_entries(self) -> None:
        """Legacy form: list of bare strings → AgentConfigs with only model set."""
        agents, models = _parse_agents(["openai/gpt-4", "anthropic/claude-3"])
        assert len(agents) == 2
        assert [a.id for a in agents] == ["agent-0", "agent-1"]
        assert [a.model for a in agents] == ["openai/gpt-4", "anthropic/claude-3"]
        assert all(a.temperature is None for a in agents)
        assert all(a.max_tokens is None for a in agents)
        assert all(a.system_prompt is None for a in agents)
        assert models == ["openai/gpt-4", "anthropic/claude-3"]

    def test_dict_entries_thread_overrides(self) -> None:
        """Dict form routes temperature / max_tokens / system_prompt to AgentConfig."""
        agents, models = _parse_agents([
            {
                "model": "openai/gpt-4",
                "temperature": 0.2,
                "max_tokens": 1024,
                "system_prompt": "Be precise.",
            },
            {"model": "anthropic/claude-3", "temperature": 0.9},
        ])
        assert agents[0].model == "openai/gpt-4"
        assert agents[0].temperature == 0.2
        assert agents[0].max_tokens == 1024
        assert agents[0].system_prompt == "Be precise."
        assert agents[1].model == "anthropic/claude-3"
        assert agents[1].temperature == 0.9
        assert agents[1].max_tokens is None
        assert agents[1].system_prompt is None
        assert models == ["openai/gpt-4", "anthropic/claude-3"]

    def test_mixed_string_and_dict_entries(self) -> None:
        """String and dict entries may be mixed in the same list."""
        agents, models = _parse_agents([
            "openai/gpt-4",
            {"model": "anthropic/claude-3", "temperature": 0.1},
        ])
        assert agents[0].model == "openai/gpt-4"
        assert agents[0].temperature is None
        assert agents[1].model == "anthropic/claude-3"
        assert agents[1].temperature == 0.1
        assert models == ["openai/gpt-4", "anthropic/claude-3"]

    def test_dict_without_model_raises(self) -> None:
        with pytest.raises(ValueError, match="missing or empty 'model' key"):
            _parse_agents([{"temperature": 0.5}])

    def test_dict_with_empty_model_raises(self) -> None:
        with pytest.raises(ValueError, match="missing or empty 'model' key"):
            _parse_agents([{"model": ""}])

    def test_invalid_entry_type_raises(self) -> None:
        with pytest.raises(ValueError, match="must be a string or dict"):
            _parse_agents([42])  # type: ignore[list-item]


class TestRichYamlThreadsToCouncil:
    """End-to-end: rich per-agent + per-meta-judge YAML reaches AgentConfig and MetaJudge."""

    @pytest.mark.filterwarnings("ignore::FutureWarning")
    async def test_per_agent_overrides_reach_agent_config(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
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
            round_history: tuple[object, ...] = ()

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
            "name": "rich_agents",
            "dataset": "gsm8k",
            "task_limit": 1,
            "council": {
                "models": [
                    {"model": "fake/a", "temperature": 0.1, "system_prompt": "A-prompt"},
                    {"model": "fake/b", "max_tokens": 512},
                    "fake/c",
                ],
                "max_rounds": 0,
                "protocol": "direct",
                "aggregation": "majority_vote",
                "termination": "fixed",
                "task_delay_seconds": 0,
            },
        }
        await runmod.run_experiment(cfg)
        agents = captured["agents"]
        assert isinstance(agents, list)
        assert len(agents) == 3
        assert agents[0].model == "fake/a"
        assert agents[0].temperature == 0.1
        assert agents[0].system_prompt == "A-prompt"
        assert agents[1].model == "fake/b"
        assert agents[1].max_tokens == 512
        assert agents[2].model == "fake/c"
        assert agents[2].temperature is None
        assert agents[2].system_prompt is None

    @pytest.mark.filterwarnings("ignore::FutureWarning")
    async def test_meta_judge_dict_reaches_metajudge(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        import council.core
        import experiments.run as runmod
        from council.aggregation import MetaJudge
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
            round_history: tuple[object, ...] = ()

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
            "name": "rich_judge",
            "dataset": "gsm8k",
            "task_limit": 1,
            "council": {
                "models": ["fake/a", "fake/b"],
                "max_rounds": 0,
                "protocol": "direct",
                "aggregation": "meta_judge",
                "meta_judge": {
                    "model": "fake/judge",
                    "temperature": 0.05,
                    "max_tokens": 4096,
                    "system_prompt": "You are the synthesis judge.",
                },
                "termination": "fixed",
                "task_delay_seconds": 0,
            },
        }
        await runmod.run_experiment(cfg)
        agg = captured["aggregation"]
        assert isinstance(agg, MetaJudge)
        assert agg._model == "fake/judge"  # type: ignore[attr-defined]
        assert agg._temperature == 0.05  # type: ignore[attr-defined]
        assert agg._max_tokens == 4096  # type: ignore[attr-defined]
        assert agg._system_prompt == "You are the synthesis judge."  # type: ignore[attr-defined]

    @pytest.mark.filterwarnings("ignore::FutureWarning")
    async def test_meta_judge_receives_output_schema(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """output_schema is forwarded to MetaJudge so it can inject JSON instructions."""
        import council.core
        import experiments.run as runmod
        from council.aggregation import MetaJudge
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
            round_history: tuple[object, ...] = ()

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
            "name": "schema_test",
            "dataset": "gsm8k",
            "task_limit": 1,
            "council": {
                "models": ["fake/a", "fake/b"],
                "max_rounds": 0,
                "protocol": "direct",
                "aggregation": "meta_judge",
                "meta_judge": {"model": "fake/judge"},
                "termination": "fixed",
                "task_delay_seconds": 0,
            },
        }
        await runmod.run_experiment(cfg)
        agg = captured["aggregation"]
        assert isinstance(agg, MetaJudge)
        # GSM8K profile has an output_schema — it must be forwarded to MetaJudge.
        assert agg._output_schema is not None  # type: ignore[attr-defined]
        assert "answer" in str(agg._output_schema)  # type: ignore[attr-defined]


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

    def test_fast_config_uses_rich_per_agent_form(self) -> None:
        """fast.yaml demonstrates the dict form (model + temperature + system_prompt)."""
        cfg = load_config("configs/experiment/fast.yaml")
        models = cfg["council"]["models"]
        # At least one entry must be a dict with model + temperature — proves the
        # rich form is documented and parseable.
        dict_entries = [m for m in models if isinstance(m, dict)]
        assert dict_entries, "fast.yaml should demonstrate the dict form for council.models"
        first = dict_entries[0]
        assert "model" in first and isinstance(first["model"], str)
        assert "temperature" in first
        # At least one entry must also carry a system_prompt to exercise that field.
        assert any("system_prompt" in m for m in dict_entries)

    def test_fast_config_has_rich_meta_judge(self) -> None:
        """fast.yaml uses the nested meta_judge dict, not the legacy bare string."""
        cfg = load_config("configs/experiment/fast.yaml")
        mj = cfg["council"].get("meta_judge")
        assert isinstance(mj, dict), "fast.yaml should use the meta_judge: {...} form"
        assert "model" in mj and isinstance(mj["model"], str)
        assert "temperature" in mj
        assert "system_prompt" in mj

    def test_fast_config_parses_into_agent_configs(self) -> None:
        """Smoke: fast.yaml models list parses into AgentConfigs with overrides."""
        cfg = load_config("configs/experiment/fast.yaml")
        agents, _ = _parse_agents(cfg["council"]["models"])
        assert len(agents) == len(cfg["council"]["models"])
        # At least one agent carries a non-default temperature sourced from YAML.
        assert any(a.temperature is not None for a in agents)
        assert any(a.system_prompt for a in agents)
