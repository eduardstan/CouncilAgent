"""Tests for evaluation/baselines.py."""

from __future__ import annotations

import pytest

from council.context import AgentResponse
from council.normalizer import IdentityNormalizer, StructuredOutputNormalizer
from evaluation.baselines import (
    BaselineResult,
    best_single_model,
    majority_vote_no_deliberation,
    oracle_best_of_n,
    random_vote,
    self_consistency,
)


def _resp(content: str, agent_id: str = "a", cost: float = 0.0) -> AgentResponse:
    return AgentResponse(
        agent_id=agent_id,
        content=content,
        round_index=0,
        tokens_in=5,
        tokens_out=3,
        cost=cost,
    )


_NORM = IdentityNormalizer()


# ---------------------------------------------------------------------------
# BaselineResult contract
# ---------------------------------------------------------------------------


def test_baseline_result_is_frozen() -> None:
    r = BaselineResult(name="x", answer="y", accuracy=1.0, cost=0.0)
    with pytest.raises((AttributeError, TypeError)):
        r.name = "z"  # type: ignore[misc]


def test_baseline_result_has_cost_field() -> None:
    r = BaselineResult(name="x", answer="y", accuracy=None, cost=0.0)
    assert r.cost == 0.0  # cost is always present, even when None is not valid


# ---------------------------------------------------------------------------
# majority_vote_no_deliberation
# ---------------------------------------------------------------------------


class TestMajorityVoteNoDeliberation:
    async def test_plurality_winner(self) -> None:
        responses = [_resp("72"), _resp("72"), _resp("75")]
        result = await majority_vote_no_deliberation(responses, _NORM)
        assert result.answer == "72"
        assert result.name == "majority_vote_no_deliberation"

    async def test_all_same_answer(self) -> None:
        responses = [_resp("Paris"), _resp("PARIS"), _resp("paris")]
        result = await majority_vote_no_deliberation(responses, _NORM)
        assert result.answer == "paris"

    async def test_empty_returns_empty(self) -> None:
        result = await majority_vote_no_deliberation([], _NORM)
        assert result.answer == ""
        assert result.accuracy is None

    async def test_with_ground_truth_correct(self) -> None:
        responses = [_resp("72"), _resp("72"), _resp("75")]
        result = await majority_vote_no_deliberation(responses, _NORM, ground_truth="72")
        assert result.accuracy == pytest.approx(1.0)

    async def test_with_ground_truth_wrong(self) -> None:
        responses = [_resp("75"), _resp("75"), _resp("72")]
        result = await majority_vote_no_deliberation(responses, _NORM, ground_truth="72")
        assert result.accuracy == pytest.approx(0.0)

    async def test_cost_is_zero(self) -> None:
        result = await majority_vote_no_deliberation([_resp("x", cost=1.0)], _NORM)
        assert result.cost == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# best_single_model
# ---------------------------------------------------------------------------


class TestBestSingleModel:
    async def test_finds_correct_response(self) -> None:
        responses = [_resp("wrong"), _resp("72"), _resp("also_wrong")]
        result = await best_single_model(responses, _NORM, ground_truth="72")
        assert result.accuracy == pytest.approx(1.0)
        assert result.answer == "72"

    async def test_no_correct_response_returns_first(self) -> None:
        responses = [_resp("wrong1"), _resp("wrong2")]
        result = await best_single_model(responses, _NORM, ground_truth="72")
        assert result.accuracy == pytest.approx(0.0)
        assert result.answer == "wrong1"

    async def test_empty_returns_empty(self) -> None:
        result = await best_single_model([], _NORM, ground_truth="72")
        assert result.answer == ""

    async def test_no_ground_truth_accuracy_is_none(self) -> None:
        result = await best_single_model([_resp("x")], _NORM)
        assert result.accuracy is None


# ---------------------------------------------------------------------------
# oracle_best_of_n
# ---------------------------------------------------------------------------


class TestOracleBestOfN:
    async def test_selects_correct_response(self) -> None:
        responses = [_resp("alpha"), _resp("72"), _resp("gamma")]
        result = await oracle_best_of_n(responses, _NORM, ground_truth="72")
        assert result.accuracy == pytest.approx(1.0)
        assert result.name == "oracle_best_of_n"

    async def test_no_correct_response_returns_zero(self) -> None:
        responses = [_resp("alpha"), _resp("beta")]
        result = await oracle_best_of_n(responses, _NORM, ground_truth="72")
        assert result.accuracy == pytest.approx(0.0)

    async def test_empty_returns_zero_accuracy(self) -> None:
        result = await oracle_best_of_n([], _NORM, ground_truth="72")
        assert result.accuracy == pytest.approx(0.0)

    async def test_cost_field_present(self) -> None:
        result = await oracle_best_of_n([_resp("x")], _NORM, ground_truth="72")
        assert isinstance(result.cost, float)


# ---------------------------------------------------------------------------
# random_vote
# ---------------------------------------------------------------------------


class TestRandomVote:
    async def test_deterministic_with_seed(self) -> None:
        responses = [_resp("A"), _resp("B"), _resp("C")]
        r1 = await random_vote(responses, _NORM, seed=42)
        r2 = await random_vote(responses, _NORM, seed=42)
        assert r1.answer == r2.answer

    async def test_empty_returns_empty(self) -> None:
        result = await random_vote([], _NORM)
        assert result.answer == ""

    async def test_cost_is_zero(self) -> None:
        result = await random_vote([_resp("x", cost=5.0)], _NORM)
        assert result.cost == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# self_consistency
# ---------------------------------------------------------------------------


class TestSelfConsistency:
    async def test_same_as_majority_vote(self) -> None:
        responses = [_resp("A"), _resp("A"), _resp("B")]
        result = await self_consistency(responses, _NORM)
        assert result.answer == "a"  # IdentityNormalizer lowercases
        assert result.name == "self_consistency"


# ---------------------------------------------------------------------------
# All baselines have cost field (§7: cost is first-class)
# ---------------------------------------------------------------------------


async def test_all_baselines_have_cost_field() -> None:
    responses = [_resp("72"), _resp("72"), _resp("75")]
    results = [
        await majority_vote_no_deliberation(responses, _NORM),
        await best_single_model(responses, _NORM),
        await oracle_best_of_n(responses, _NORM, ground_truth="72"),
        await random_vote(responses, _NORM),
        await self_consistency(responses, _NORM),
    ]
    for r in results:
        assert isinstance(r.cost, float), f"{r.name} missing float cost"
