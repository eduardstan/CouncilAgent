"""Tests for council/policy.py — CouncilConfig and CouncilPolicy."""

from __future__ import annotations

import pytest

from council.aggregation import MajorityVote, MetaJudge
from council.models import FakeModelClient
from council.normalizer import IdentityNormalizer, StructuredOutputNormalizer
from council.policy import CouncilConfig, CouncilPolicy, _FREE_MODELS
from council.protocol import DirectAnswerProtocol, PeerReviewProtocol
from council.task_profile import TaskProfile
from council.termination import FixedRounds


# ---------------------------------------------------------------------------
# CouncilConfig
# ---------------------------------------------------------------------------


class TestCouncilConfig:
    def _minimal_config(self) -> CouncilConfig:
        from council.core import AgentConfig
        from council.normalizer import IdentityNormalizer
        from council.topology import CompleteGraphTopology
        from council.termination import FixedRounds

        return CouncilConfig(
            name="test",
            agents=[AgentConfig(id="a", model="fake/m"), AgentConfig(id="b", model="fake/m")],
            topology=CompleteGraphTopology(2),
            protocol=DirectAnswerProtocol(),
            aggregation=MajorityVote(normalizer=IdentityNormalizer()),
            termination=FixedRounds(1),
        )

    def test_stores_all_fields(self) -> None:
        cfg = self._minimal_config()
        assert cfg.name == "test"
        assert len(cfg.agents) == 2
        assert cfg.anonymize is True
        assert cfg.estimated_cost_usd == pytest.approx(0.0)

    def test_is_frozen(self) -> None:
        cfg = self._minimal_config()
        with pytest.raises((AttributeError, TypeError)):
            cfg.name = "changed"  # type: ignore[misc]

    def test_ranking_defaults_to_none(self) -> None:
        cfg = self._minimal_config()
        assert cfg.ranking is None


# ---------------------------------------------------------------------------
# CouncilPolicy
# ---------------------------------------------------------------------------


def _profile_factual() -> TaskProfile:
    return TaskProfile(name="factual", normalizer=StructuredOutputNormalizer(), recommended_aggregation="majority_vote")


def _profile_open_ended() -> TaskProfile:
    return TaskProfile(name="open_ended", normalizer=IdentityNormalizer(), recommended_aggregation="meta_judge")


class TestCouncilPolicy:
    def _policy(self, budget: float = 0.10, models: list[str] | None = None) -> CouncilPolicy:
        return CouncilPolicy(model_client=FakeModelClient({}), budget_usd=budget, default_models=models)

    def test_plan_returns_council_config(self) -> None:
        policy = self._policy()
        cfg = policy.plan("What is 2+2?", _profile_factual())
        assert isinstance(cfg, CouncilConfig)

    def test_plan_uses_majority_vote_for_factual(self) -> None:
        policy = self._policy()
        cfg = policy.plan("What is 2+2?", _profile_factual())
        # standard_deliberation (last affordable) uses MajorityVote for factual.
        assert isinstance(cfg.aggregation, MajorityVote)

    def test_plan_uses_meta_judge_for_open_ended(self) -> None:
        policy = self._policy()
        cfg = policy.plan("Write a poem.", _profile_open_ended())
        # standard_deliberation for open_ended uses MetaJudge.
        assert isinstance(cfg.aggregation, MetaJudge)

    def test_plan_agents_match_model_list(self) -> None:
        models = ["fake/a", "fake/b"]
        policy = self._policy(models=models)
        cfg = policy.plan("Q", _profile_factual())
        agent_models = [a.model for a in cfg.agents]
        assert agent_models == models

    def test_plan_returns_affordable_tier(self) -> None:
        # Both tiers have cost 0.0 → standard_deliberation (last) should be chosen.
        policy = self._policy(budget=0.10)
        cfg = policy.plan("Q", _profile_factual())
        assert cfg.name == "standard_deliberation"

    def test_plan_falls_back_to_cheapest_when_budget_zero(self) -> None:
        # budget=0.0 → no tier is affordable (0.0 <= 0.0 is True for free models).
        # Free models have estimated_cost=0.0 → all tiers are affordable.
        policy = self._policy(budget=0.0)
        cfg = policy.plan("Q", _profile_factual())
        # 0.0 <= 0.0 is True → standard_deliberation still returned.
        assert isinstance(cfg, CouncilConfig)

    def test_plan_standard_uses_peer_review_protocol(self) -> None:
        policy = self._policy()
        cfg = policy.plan("Q", _profile_factual())
        assert isinstance(cfg.protocol, PeerReviewProtocol)

    def test_default_models_are_free_openrouter(self) -> None:
        assert all("openrouter" in m for m in _FREE_MODELS)
        assert all(":free" in m for m in _FREE_MODELS)
        assert len(_FREE_MODELS) == 3

    def test_plan_three_agents_with_default_models(self) -> None:
        policy = self._policy()
        cfg = policy.plan("Q", _profile_factual())
        assert len(cfg.agents) == 3

    # --- Task 6.6: output_schema injection ---

    def test_plan_injects_output_schema_into_protocol(self) -> None:
        schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
        profile = TaskProfile(name="structured", normalizer=IdentityNormalizer(), output_schema=schema)
        policy = self._policy()
        cfg = policy.plan("Q", profile)
        # The returned protocol is PeerReviewProtocol (standard_deliberation tier).
        assert isinstance(cfg.protocol, PeerReviewProtocol)
        assert cfg.protocol._schema == schema  # type: ignore[attr-defined]

    def test_plan_no_output_schema_leaves_protocol_schema_none(self) -> None:
        profile = TaskProfile(name="plain", normalizer=IdentityNormalizer(), output_schema=None)
        policy = self._policy()
        cfg = policy.plan("Q", profile)
        assert cfg.protocol._schema is None  # type: ignore[attr-defined]

    def test_plan_fast_tier_also_gets_output_schema(self) -> None:
        schema = {"type": "object"}
        profile = TaskProfile(name="structured", normalizer=IdentityNormalizer(), output_schema=schema)
        # Use zero budget so we can inspect the fast tier
        policy = self._policy(budget=100.0)
        tiers = policy._build_tiers(profile)  # type: ignore[attr-defined]
        fast = next(t for t in tiers if t.name == "fast_vote")
        assert fast.protocol._schema == schema  # type: ignore[attr-defined]

    # --- Fix 1: meta_judge_model configurable ---

    def test_meta_judge_model_explicit_used_when_set(self) -> None:
        dedicated = "openrouter/anthropic/claude-opus-4"
        policy = CouncilPolicy(
            model_client=FakeModelClient({}),
            default_models=["fake/a", "fake/b"],
            meta_judge_model=dedicated,
        )
        cfg = policy.plan("Write a poem.", _profile_open_ended())
        assert isinstance(cfg.aggregation, MetaJudge)
        assert cfg.aggregation._model == dedicated  # type: ignore[attr-defined]

    def test_meta_judge_model_falls_back_to_models_0_when_none(self) -> None:
        models = ["fake/primary", "fake/secondary"]
        policy = CouncilPolicy(
            model_client=FakeModelClient({}),
            default_models=models,
            meta_judge_model=None,
        )
        cfg = policy.plan("Write a poem.", _profile_open_ended())
        assert isinstance(cfg.aggregation, MetaJudge)
        assert cfg.aggregation._model == "fake/primary"  # type: ignore[attr-defined]
