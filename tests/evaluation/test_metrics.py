"""Tests for evaluation/metrics.py.

Regression Issue 9: task_accuracy("The answer is 172.", "72", method="smart")
must return 0.0 — word-boundary match, not substring.
"""

from __future__ import annotations

import pytest

from council.context import AgentResponse, CouncilState
from council.normalizer import IdentityNormalizer, StructuredOutputNormalizer
from evaluation.metrics import (
    communication_cost,
    convergence_rate,
    deliberation_efficiency,
    diversity_trajectory,
    inter_rater_agreement,
    task_accuracy,
)


def _resp(content: str, agent_id: str = "a", round_index: int = 0) -> AgentResponse:
    return AgentResponse(
        agent_id=agent_id,
        content=content,
        round_index=round_index,
        tokens_in=10,
        tokens_out=5,
        cost=0.0,
    )


# ---------------------------------------------------------------------------
# task_accuracy
# ---------------------------------------------------------------------------


class TestTaskAccuracy:
    async def test_issue9_regression_word_boundary_no_match(self) -> None:
        """Issue 9: '172' contains '72' as substring but NOT as whole token."""
        score = await task_accuracy("The answer is 172.", "72", method="smart")
        assert score == pytest.approx(0.0)

    async def test_smart_match_exact_after_normalisation(self) -> None:
        score = await task_accuracy("The answer is 72.", "72", method="smart")
        assert score == pytest.approx(1.0)

    async def test_smart_match_word_boundary_bare(self) -> None:
        score = await task_accuracy("72", "72", method="smart")
        assert score == pytest.approx(1.0)

    async def test_smart_match_boundary_with_punctuation(self) -> None:
        # "72." — period is not alphanumeric, so "72" is a whole token
        score = await task_accuracy("The answer is 72.", "72", method="smart")
        assert score == pytest.approx(1.0)

    async def test_exact_method_case_insensitive(self) -> None:
        score = await task_accuracy("Paris", "paris", method="exact")
        assert score == pytest.approx(1.0)

    async def test_exact_method_mismatch(self) -> None:
        score = await task_accuracy("London", "paris", method="exact")
        assert score == pytest.approx(0.0)

    async def test_smart_with_structured_normalizer(self) -> None:
        norm = StructuredOutputNormalizer()
        score = await task_accuracy('{"answer": "72"}', "72", method="smart", normalizer=norm)
        assert score == pytest.approx(1.0)

    async def test_smart_no_match(self) -> None:
        score = await task_accuracy("The answer is 99.", "72", method="smart")
        assert score == pytest.approx(0.0)

    async def test_default_normalizer_is_identity(self) -> None:
        # Default normalizer lowercases + strips — "PARIS" normalises to "paris"
        score = await task_accuracy("PARIS", "paris", method="smart")
        assert score == pytest.approx(1.0)

    # --- numeric canonicalization (Task 6.4) ---

    async def test_currency_prefix_stripped(self) -> None:
        score = await task_accuracy("$70,000", "70000", method="smart")
        assert score == pytest.approx(1.0)

    async def test_currency_no_thousands_sep(self) -> None:
        score = await task_accuracy("$18", "18", method="smart")
        assert score == pytest.approx(1.0)

    async def test_euro_with_decimal(self) -> None:
        score = await task_accuracy("€1,234.56", "1234.56", method="smart")
        assert score == pytest.approx(1.0)

    async def test_currency_in_sentence(self) -> None:
        score = await task_accuracy("The answer is $70,000.", "70000", method="smart")
        assert score == pytest.approx(1.0)

    async def test_issue9_still_fails_after_canonicalize(self) -> None:
        # "172" and "72" canonicalize identically (no currency/commas) — word-boundary
        # must still reject "72" found inside "172".
        score = await task_accuracy("The answer is 172.", "72", method="smart")
        assert score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# convergence_rate
# ---------------------------------------------------------------------------


class TestConvergenceRate:
    def test_monotone_increasing(self) -> None:
        rate = convergence_rate([0.3, 0.6, 0.9, 1.0])
        assert 0.0 < rate <= 1.0

    def test_full_agreement_from_start(self) -> None:
        rate = convergence_rate([1.0, 1.0, 1.0])
        assert rate == pytest.approx(1.0)

    def test_zero_agreement_throughout(self) -> None:
        rate = convergence_rate([0.0, 0.0, 0.0])
        assert rate == pytest.approx(0.0)

    def test_single_round_returns_value(self) -> None:
        assert convergence_rate([0.75]) == pytest.approx(0.75)

    def test_empty_returns_zero(self) -> None:
        assert convergence_rate([]) == pytest.approx(0.0)

    def test_late_convergence_lower_than_early(self) -> None:
        early = convergence_rate([1.0, 1.0, 0.5])
        late = convergence_rate([0.5, 0.5, 1.0])
        assert early > late


# ---------------------------------------------------------------------------
# deliberation_efficiency
# ---------------------------------------------------------------------------


class TestDeliberationEfficiency:
    def test_positive_delta_returns_positive(self) -> None:
        eff = deliberation_efficiency(0.1, 1000)
        assert eff == pytest.approx(0.1)  # 0.1 / (1000/1000)

    def test_zero_tokens_returns_zero(self) -> None:
        assert deliberation_efficiency(0.5, 0) == pytest.approx(0.0)

    def test_negative_delta_returns_negative(self) -> None:
        assert deliberation_efficiency(-0.05, 500) < 0.0

    def test_scales_with_tokens(self) -> None:
        e1 = deliberation_efficiency(0.1, 500)
        e2 = deliberation_efficiency(0.1, 1000)
        assert e1 > e2  # same delta, fewer tokens → more efficient


# ---------------------------------------------------------------------------
# communication_cost
# ---------------------------------------------------------------------------


class TestCommunicationCost:
    def _make_state(self, rounds: int, agents: int) -> CouncilState:
        history = [
            _resp("x", agent_id=f"agent-{a}", round_index=r)
            for r in range(rounds)
            for a in range(agents)
        ]
        return CouncilState(question="test?", round_history=history)

    def test_token_sum_correct(self) -> None:
        state = self._make_state(rounds=2, agents=3)
        cost = communication_cost(state)
        # 6 responses × (tokens_in=10, tokens_out=5)
        assert cost["total_tokens_in"] == 60
        assert cost["total_tokens_out"] == 30
        assert cost["total_tokens"] == 90

    def test_api_calls_equals_total_responses(self) -> None:
        state = self._make_state(rounds=2, agents=3)
        cost = communication_cost(state)
        assert cost["api_calls"] == 6

    def test_rounds_used(self) -> None:
        state = self._make_state(rounds=2, agents=3)
        assert communication_cost(state)["rounds_used"] == 2

    def test_empty_state(self) -> None:
        state = CouncilState(question="test?", round_history=[])
        cost = communication_cost(state)
        assert cost["total_tokens"] == 0
        assert cost["api_calls"] == 0
        assert cost["rounds_used"] == 0


# ---------------------------------------------------------------------------
# inter_rater_agreement
# ---------------------------------------------------------------------------


class TestInterRaterAgreement:
    def test_perfect_agreement_returns_1(self) -> None:
        kappa = inter_rater_agreement([["A", "B", "C"], ["A", "B", "C"]])
        assert kappa == pytest.approx(1.0)

    def test_single_rater_returns_0(self) -> None:
        assert inter_rater_agreement([["A", "B"]]) == pytest.approx(0.0)

    def test_empty_returns_0(self) -> None:
        assert inter_rater_agreement([]) == pytest.approx(0.0)

    def test_opposite_rankings_negative_or_zero(self) -> None:
        kappa = inter_rater_agreement([["A", "B"], ["B", "A"]])
        # Perfect disagreement → κ = -1 or 0 depending on marginals
        assert kappa <= 0.0

    def test_three_raters_unanimous(self) -> None:
        kappa = inter_rater_agreement([["X", "Y"], ["X", "Y"], ["X", "Y"]])
        assert kappa == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# diversity_trajectory
# ---------------------------------------------------------------------------


class TestDiversityTrajectory:
    def _fake_embedder(self) -> object:
        """Returns an embedder that maps each unique string to a unique orthogonal vector.

        All emitted vectors share a fixed dimensionality so they can be
        compared with cosine distance (which requires equal lengths).
        """

        class _FakeEmbedder:
            _DIM = 16
            _vocab: dict[str, list[float]] = {}

            def encode(self, texts: list[str]) -> list[list[float]]:
                result = []
                for t in texts:
                    if t not in self._vocab:
                        idx = len(self._vocab)
                        v = [0.0] * self._DIM
                        v[idx % self._DIM] = 1.0
                        self._vocab[t] = v
                    result.append(self._vocab[t])
                return result

        return _FakeEmbedder()

    def test_requires_embedder(self) -> None:
        with pytest.raises(ValueError, match="requires an Embedder"):
            diversity_trajectory([["a", "b"]], embedder=None)

    def test_identical_responses_zero_diversity(self) -> None:
        embedder = self._fake_embedder()
        scores = diversity_trajectory([["hello", "hello"]], embedder=embedder)  # type: ignore[arg-type]
        assert scores[0] == pytest.approx(0.0)

    def test_orthogonal_responses_max_diversity(self) -> None:
        embedder = self._fake_embedder()
        # "alpha" and "beta" map to orthogonal vectors → cosine distance = 1.0
        scores = diversity_trajectory([["alpha", "beta"]], embedder=embedder)  # type: ignore[arg-type]
        assert scores[0] == pytest.approx(1.0)

    def test_single_response_zero_diversity(self) -> None:
        embedder = self._fake_embedder()
        scores = diversity_trajectory([["only"]], embedder=embedder)  # type: ignore[arg-type]
        assert scores[0] == pytest.approx(0.0)

    def test_two_rounds_returns_two_scores(self) -> None:
        embedder = self._fake_embedder()
        rounds = [["a1", "b1"], ["a2", "b2"]]
        scores = diversity_trajectory(rounds, embedder=embedder)  # type: ignore[arg-type]
        assert len(scores) == 2
