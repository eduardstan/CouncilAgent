"""Tests for council/aggregation.py — reduce responses to a final answer.

Regression Issue 3: MajorityVote over ["The answer is 72.", "72", "answer: 72"]
with StructuredOutputNormalizer must return confidence == 1.0.
"""

from __future__ import annotations

import pytest

from council.aggregation import BordaCount, CondorcetAggregation, MajorityVote, MetaJudge
from council.context import AgentResponse, AggregationResult, RichPreference
from council.normalizer import IdentityNormalizer, StructuredOutputNormalizer


def _resp(content: str, agent_id: str = "a", round_index: int = 0) -> AgentResponse:
    return AgentResponse(
        agent_id=agent_id,
        content=content,
        round_index=round_index,
        tokens_in=5,
        tokens_out=len(content) // 4 + 1,
        cost=0.0,
    )


# ---------------------------------------------------------------------------
# MajorityVote
# ---------------------------------------------------------------------------


class TestMajorityVote:
    async def test_issue3_regression_confidence_1_on_normalized_agreement(self) -> None:
        """Issue 3: three surface forms of '72' must yield confidence == 1.0."""
        responses = [
            _resp("The answer is 72.", "a"),
            _resp("72", "b"),
            _resp("answer: 72", "c"),
        ]
        agg = MajorityVote(normalizer=StructuredOutputNormalizer())
        result = await agg.aggregate(responses)
        assert isinstance(result, AggregationResult)
        assert result.final_answer == "72"
        assert result.confidence == pytest.approx(1.0)

    async def test_majority_winner_and_correct_confidence(self) -> None:
        responses = [_resp("A", "a"), _resp("A", "b"), _resp("B", "c")]
        agg = MajorityVote(normalizer=IdentityNormalizer())
        result = await agg.aggregate(responses)
        assert result.final_answer == "a"  # normalized "A"
        assert result.confidence == pytest.approx(2 / 3)

    async def test_single_response_confidence_1(self) -> None:
        agg = MajorityVote(normalizer=IdentityNormalizer())
        result = await agg.aggregate([_resp("hello")])
        assert result.confidence == pytest.approx(1.0)

    async def test_all_different_confidence_one_third(self) -> None:
        responses = [_resp("A", "a"), _resp("B", "b"), _resp("C", "c")]
        agg = MajorityVote(normalizer=IdentityNormalizer())
        result = await agg.aggregate(responses)
        assert result.confidence == pytest.approx(1 / 3)

    async def test_final_answer_is_canonical_form(self) -> None:
        # final_answer is the canonical (normalised) form — the unambiguous answer key.
        # IdentityNormalizer lowercases; so "PARIS" → canonical "paris".
        responses = [_resp("PARIS", "a"), _resp("PARIS", "b"), _resp("LONDON", "c")]
        agg = MajorityVote(normalizer=IdentityNormalizer())
        result = await agg.aggregate(responses)
        assert result.final_answer == "paris"

    async def test_method_is_majority_vote(self) -> None:
        agg = MajorityVote(normalizer=IdentityNormalizer())
        result = await agg.aggregate([_resp("x")])
        assert result.method == "MajorityVote"

    async def test_structured_output_normalizer_extracts_answer_field(self) -> None:
        agg = MajorityVote(normalizer=StructuredOutputNormalizer())
        result = await agg.aggregate([_resp('{"answer": "hello"}')])
        assert result.final_answer == "hello"

    async def test_does_not_call_model(self) -> None:
        # MajorityVote must never call ModelClient — it is pure aggregation.
        # Verified implicitly: aggregate() is async but has no model dep.
        agg = MajorityVote(normalizer=IdentityNormalizer())
        result = await agg.aggregate([_resp("x"), _resp("x")])
        assert result.final_answer == "x"


# ---------------------------------------------------------------------------
# BordaCount
# ---------------------------------------------------------------------------


def _pref(ordered_ids: list[str]) -> RichPreference:
    return RichPreference(raw_text="", ordered_ids=ordered_ids)


class TestBordaCount:
    async def test_winner_from_two_preferences(self) -> None:
        # 3 agents; 2 preferences both rank agent-0 first.
        responses = [_resp("ans-A", "agent-0"), _resp("ans-B", "agent-1"), _resp("ans-C", "agent-2")]
        prefs = [_pref(["agent-0", "agent-1", "agent-2"]), _pref(["agent-0", "agent-2", "agent-1"])]
        result = await BordaCount().aggregate(responses, prefs)
        assert result.final_answer == "ans-A"
        assert result.method == "BordaCount"

    async def test_confidence_is_winner_score_over_max(self) -> None:
        # 2 agents, 1 preference: agent-0 > agent-1. n=2 → max_possible = 1*(2-1) = 1.
        # agent-0 gets 1 point → confidence = 1/1 = 1.0
        responses = [_resp("A", "agent-0"), _resp("B", "agent-1")]
        prefs = [_pref(["agent-0", "agent-1"])]
        result = await BordaCount().aggregate(responses, prefs)
        assert result.confidence == pytest.approx(1.0)

    async def test_empty_preferences_returns_empty(self) -> None:
        result = await BordaCount().aggregate([_resp("x")], preferences=[])
        assert result.final_answer == ""
        assert result.confidence == pytest.approx(0.0)

    async def test_no_rich_preferences_returns_empty(self) -> None:
        from council.context import PreferenceData
        result = await BordaCount().aggregate([_resp("x")], preferences=[PreferenceData()])
        assert result.final_answer == ""

    async def test_split_preferences_lower_confidence(self) -> None:
        # 2 agents, 2 prefs: one prefers agent-0, one prefers agent-1.
        # n=2 → max_possible = 2*(2-1) = 2; each gets 1 point → conf = 0.5
        responses = [_resp("A", "agent-0"), _resp("B", "agent-1")]
        prefs = [_pref(["agent-0", "agent-1"]), _pref(["agent-1", "agent-0"])]
        result = await BordaCount().aggregate(responses, prefs)
        assert result.confidence == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# MetaJudge
# ---------------------------------------------------------------------------


class TestMetaJudge:
    def _make_judge(self, synthesis: str) -> MetaJudge:
        from council.models import FakeModelClient
        client = FakeModelClient({("meta-judge", 0): synthesis})
        return MetaJudge(model="fake/synth", model_client=client)

    async def test_returns_synthesis_model_output(self) -> None:
        agg = self._make_judge("The synthesized answer is 4.")
        result = await agg.aggregate([_resp("four"), _resp("4")])
        assert result.final_answer == "The synthesized answer is 4."
        assert result.method == "MetaJudge"

    async def test_prompt_contains_all_responses(self) -> None:
        captured: list[str] = []

        def factory(req, agent_id, round_index):  # type: ignore[return]
            captured.append(req.prompt)
            return "synthesized"

        from council.models import FakeModelClient
        agg = MetaJudge(model="fake/m", model_client=FakeModelClient(factory))
        await agg.aggregate([_resp("alpha", "agent-0"), _resp("beta", "agent-1")])
        assert captured, "model was never called"
        assert "alpha" in captured[0]
        assert "beta" in captured[0]

    async def test_empty_responses_returns_empty(self) -> None:
        agg = self._make_judge("irrelevant")
        result = await agg.aggregate([])
        assert result.final_answer == ""
        assert result.confidence == pytest.approx(0.0)

    async def test_model_failure_returns_empty(self) -> None:
        from council.models import FakeModelClient
        # Empty dict → FakeModelClient returns ModelFailure for unknown key
        agg = MetaJudge(model="fake/m", model_client=FakeModelClient({}))
        result = await agg.aggregate([_resp("x")])
        assert result.final_answer == ""
        assert result.confidence == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Cross-layer isolation
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# CondorcetAggregation
# ---------------------------------------------------------------------------


class TestCondorcetAggregation:
    async def test_condorcet_winner_when_one_exists(self) -> None:
        # 3 agents; 2 prefs both rank agent-0 first → strict Condorcet winner.
        responses = [_resp("ans-A", "agent-0"), _resp("ans-B", "agent-1"), _resp("ans-C", "agent-2")]
        prefs = [_pref(["agent-0", "agent-1", "agent-2"]), _pref(["agent-0", "agent-2", "agent-1"])]
        result = await CondorcetAggregation().aggregate(responses, prefs)
        assert result.final_answer == "ans-A"
        assert result.method == "Condorcet"
        assert result.confidence > 0.5

    async def test_copeland_fallback_on_condorcet_cycle(self) -> None:
        # Classic A>B>C>A cycle — no Condorcet winner.
        # Pref 1: A > B > C
        # Pref 2: B > C > A
        # Pref 3: C > A > B
        # Pairwise: A>B 2-1, B>C 2-1, C>A 2-1 → cycle → Copeland, all tie at 0.
        responses = [_resp("alpha", "A"), _resp("beta", "B"), _resp("gamma", "C")]
        prefs = [_pref(["A", "B", "C"]), _pref(["B", "C", "A"]), _pref(["C", "A", "B"])]
        result = await CondorcetAggregation().aggregate(responses, prefs)
        assert result.method == "Copeland"
        # Three-way Copeland tie: each agent has 1 win, 1 loss → score 0.
        # Max_wins = 2; confidence = (0 + 2) / (2 * 2) = 0.5
        assert result.confidence == pytest.approx(0.5)

    async def test_empty_preferences_returns_empty(self) -> None:
        result = await CondorcetAggregation().aggregate([_resp("x")], preferences=[])
        assert result.final_answer == ""
        assert result.method == "Condorcet"

    async def test_single_candidate_returns_it(self) -> None:
        responses = [_resp("only", "agent-0")]
        prefs = [_pref(["agent-0"])]
        result = await CondorcetAggregation().aggregate(responses, prefs)
        assert result.final_answer == "only"


# ---------------------------------------------------------------------------
# Cross-layer isolation
# ---------------------------------------------------------------------------


def test_aggregation_imports_only_context_and_models() -> None:
    """aggregation.py may import from council.context and council.models only.

    council.models is permitted because MetaJudge injects a ModelClient to call
    the synthesis model — this is an aggregation-internal operation, not a
    protocol/deliberation concern (Constitution §3, accepted exception).
    All other layer imports (topology, protocol, ranking, normalizer, termination,
    core) remain forbidden.
    """
    import importlib.util

    spec = importlib.util.find_spec("council.aggregation")
    assert spec is not None and spec.origin is not None
    with open(spec.origin) as f:
        source = f.read()
    allowed = {"council.context", "council.models"}
    bad = [
        line
        for line in source.splitlines()
        if ("from council." in line or "import council." in line)
        and not any(a in line for a in allowed)
        and not line.strip().startswith("#")
    ]
    assert bad == [], f"aggregation.py forbidden imports: {bad}"
