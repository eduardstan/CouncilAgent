"""Tests for council/termination.py

Regression Issue 10: AgreementThreshold(0.8) on a state where 3/3 agents
normalized to "72" must return (True, ...).

Architecture §3: termination reads CouncilState only; must not import other
layer modules.
"""

from __future__ import annotations

import pytest

from council.context import AgentResponse, CouncilState
from council.normalizer import IdentityNormalizer, StructuredOutputNormalizer
from council.termination import (
    AgreementThreshold,
    BudgetExhaustion,
    CompositeTermination,
    FixedRounds,
    TerminationStrategy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state_with_responses(
    contents: list[str],
    *,
    round_index: int = 0,
    current_round: int = 1,
    total_cost: float = 0.0,
) -> CouncilState:
    state = CouncilState.initial("test question")
    for i, content in enumerate(contents):
        state.round_history.append(
            AgentResponse(
                agent_id=f"agent-{i}",
                content=content,
                round_index=round_index,
                tokens_in=5,
                tokens_out=5,
                cost=total_cost / max(len(contents), 1),
            )
        )
    state.current_round = current_round
    state.total_cost = total_cost
    return state


# ---------------------------------------------------------------------------
# FixedRounds
# ---------------------------------------------------------------------------


class TestFixedRounds:
    async def test_stops_at_max_rounds(self) -> None:
        state = _state_with_responses(["x"], current_round=3)
        strategy = FixedRounds(max_rounds=3)
        stop, reason = await strategy.should_stop(state)
        assert stop
        assert "3" in reason

    async def test_continues_before_max_rounds(self) -> None:
        state = _state_with_responses(["x"], current_round=1)
        strategy = FixedRounds(max_rounds=3)
        stop, _ = await strategy.should_stop(state)
        assert not stop

    async def test_single_round(self) -> None:
        state = _state_with_responses(["x"], current_round=1)
        strategy = FixedRounds(max_rounds=1)
        stop, _ = await strategy.should_stop(state)
        assert stop

    def test_invalid_max_rounds(self) -> None:
        with pytest.raises(ValueError):
            FixedRounds(0)


# ---------------------------------------------------------------------------
# AgreementThreshold — Issue 10 regression
# ---------------------------------------------------------------------------


class TestAgreementThreshold:
    async def test_issue10_regression_consensus_stops(self) -> None:
        """Issue 10: 3/3 agents normalized to '72' → threshold=0.8 → should stop."""
        state = _state_with_responses(
            ["The answer is 72.", "72", "answer: 72"],
            current_round=1,
        )
        strategy = AgreementThreshold(0.8, normalizer=StructuredOutputNormalizer())
        stop, reason = await strategy.should_stop(state)
        assert stop
        assert "100%" in reason

    async def test_below_threshold_continues(self) -> None:
        state = _state_with_responses(["A", "B", "C"], current_round=1)
        strategy = AgreementThreshold(0.8, normalizer=IdentityNormalizer())
        stop, _ = await strategy.should_stop(state)
        assert not stop

    async def test_exact_threshold_stops(self) -> None:
        # 2/2 = 100% >= 80%
        state = _state_with_responses(["yes", "yes"], current_round=1)
        strategy = AgreementThreshold(0.8, normalizer=IdentityNormalizer())
        stop, _ = await strategy.should_stop(state)
        assert stop

    async def test_two_thirds_agreement_below_80(self) -> None:
        state = _state_with_responses(["yes", "yes", "no"], current_round=1)
        strategy = AgreementThreshold(0.8, normalizer=IdentityNormalizer())
        stop, _ = await strategy.should_stop(state)
        assert not stop  # 67% < 80%

    async def test_two_thirds_agreement_above_60(self) -> None:
        state = _state_with_responses(["yes", "yes", "no"], current_round=1)
        strategy = AgreementThreshold(0.6, normalizer=IdentityNormalizer())
        stop, _ = await strategy.should_stop(state)
        assert stop  # 67% >= 60%

    async def test_empty_round_continues(self) -> None:
        # current_round=1 but no responses at round_index=0
        state = CouncilState.initial("q")
        state.current_round = 1
        strategy = AgreementThreshold(0.5, normalizer=IdentityNormalizer())
        stop, _ = await strategy.should_stop(state)
        assert not stop

    async def test_reason_contains_percentages(self) -> None:
        state = _state_with_responses(["yes", "yes"], current_round=1)
        strategy = AgreementThreshold(0.5, normalizer=IdentityNormalizer())
        stop, reason = await strategy.should_stop(state)
        assert stop
        assert "%" in reason

    def test_invalid_threshold(self) -> None:
        with pytest.raises(ValueError):
            AgreementThreshold(0.0, normalizer=IdentityNormalizer())

    def test_threshold_above_one_invalid(self) -> None:
        with pytest.raises(ValueError):
            AgreementThreshold(1.1, normalizer=IdentityNormalizer())


# ---------------------------------------------------------------------------
# BudgetExhaustion
# ---------------------------------------------------------------------------


class TestBudgetExhaustion:
    async def test_stops_when_budget_reached(self) -> None:
        state = _state_with_responses(["x"], total_cost=0.10)
        strategy = BudgetExhaustion(budget_usd=0.05)
        stop, reason = await strategy.should_stop(state)
        assert stop
        assert "$" in reason

    async def test_continues_under_budget(self) -> None:
        state = _state_with_responses(["x"], total_cost=0.01)
        strategy = BudgetExhaustion(budget_usd=0.05)
        stop, _ = await strategy.should_stop(state)
        assert not stop

    async def test_exact_budget_stops(self) -> None:
        state = _state_with_responses(["x"], total_cost=0.05)
        strategy = BudgetExhaustion(budget_usd=0.05)
        stop, _ = await strategy.should_stop(state)
        assert stop

    def test_invalid_budget(self) -> None:
        with pytest.raises(ValueError):
            BudgetExhaustion(0.0)


# ---------------------------------------------------------------------------
# CompositeTermination
# ---------------------------------------------------------------------------


class TestCompositeTermination:
    async def test_stops_when_any_strategy_stops(self) -> None:
        state = _state_with_responses(["x"], current_round=3)
        composite = CompositeTermination(
            FixedRounds(10),   # would not stop
            FixedRounds(3),    # stops
        )
        stop, reason = await composite.should_stop(state)
        assert stop
        assert "3" in reason

    async def test_continues_when_no_strategy_stops(self) -> None:
        state = _state_with_responses(["x"], current_round=1)
        composite = CompositeTermination(
            FixedRounds(5),
            FixedRounds(10),
        )
        stop, _ = await composite.should_stop(state)
        assert not stop

    async def test_first_matching_strategy_wins(self) -> None:
        state = _state_with_responses(["x"], current_round=3, total_cost=1.0)
        composite = CompositeTermination(
            BudgetExhaustion(0.5),  # stops first
            FixedRounds(3),         # also stops, but second
        )
        stop, reason = await composite.should_stop(state)
        assert stop
        assert "budget" in reason

    def test_empty_strategies_raises(self) -> None:
        with pytest.raises(ValueError):
            CompositeTermination()


# ---------------------------------------------------------------------------
# Cross-layer isolation
# ---------------------------------------------------------------------------


def test_termination_only_imports_context() -> None:
    import importlib.util

    spec = importlib.util.find_spec("council.termination")
    assert spec is not None and spec.origin is not None
    with open(spec.origin) as f:
        source = f.read()
    allowed = {"council.context"}
    bad = [
        line
        for line in source.splitlines()
        if ("from council." in line or "import council." in line)
        and not any(a in line for a in allowed)
        and not line.strip().startswith("#")
    ]
    assert bad == [], f"termination.py forbidden imports: {bad}"
