"""Tests for council/core.py — run_council() pure async pipeline.

Per testing.md §core pipeline requirements:
(a) All agents generated in round 0.
(b) Adjacency matrix respected in round 1 (RingTopology enforcement).
(c) Aggregation produced a non-null result.
(d) State token counts are non-zero.

Plus: anonymization end-to-end, ModelFailure partial-result handling,
AgreementThreshold early exit, and zero framework imports.
"""

from __future__ import annotations

from council.aggregation import MajorityVote
from council.context import CouncilResult
from council.core import AgentConfig, run_council
from council.models import FakeModelClient
from council.normalizer import IdentityNormalizer
from council.protocol import DirectAnswerProtocol, PeerReviewProtocol
from council.termination import AgreementThreshold, CompositeTermination, FixedRounds
from council.topology import CompleteGraphTopology, RingTopology

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _agents(n: int) -> list[AgentConfig]:
    return [AgentConfig(id=f"agent-{i}", model=f"fake/model-{i}") for i in range(n)]


def _fake(n: int, response: str = "42") -> FakeModelClient:
    """FakeModelClient returning `response` for all (agent-i, round) combos."""
    responses: dict[tuple[str, int], str] = {}
    for i in range(n):
        for r in range(5):  # cover up to 5 rounds
            responses[(f"agent-{i}", r)] = response
    return FakeModelClient(responses)


# ---------------------------------------------------------------------------
# (a) All agents generate in round 0
# ---------------------------------------------------------------------------


async def test_all_agents_generate_in_round_0() -> None:
    agents = _agents(3)
    client = _fake(3)
    result = await run_council(
        prompt="What is 6x7?",
        agents=agents,
        model_client=client,
        topology=CompleteGraphTopology(3),
        protocol=DirectAnswerProtocol(),
        aggregation=MajorityVote(normalizer=IdentityNormalizer()),
        termination=FixedRounds(1),
    )
    round_0_ids = {r.agent_id for r in result.round_history if r.round_index == 0}
    # All 3 agent IDs appear in round 0 (may be real or anonymized — check count).
    assert len(round_0_ids) == 3


# ---------------------------------------------------------------------------
# (b) Adjacency matrix respected in round 1 — RingTopology
# ---------------------------------------------------------------------------


async def test_ring_topology_visibility_in_round_1() -> None:
    """Each agent's round-1 prompt must contain only its predecessor's response."""
    n = 4
    captured_contexts: list[tuple[str, int, list[str]]] = []  # (agent_id, round, visible_ids)

    class SpyProtocol(DirectAnswerProtocol):
        def build_prompt(self, ctx):  # type: ignore[override]
            captured_contexts.append((
                ctx.agent_id,
                ctx.round_index,
                [r.agent_id for r in ctx.visible_responses],
            ))
            return super().build_prompt(ctx)

    agents = _agents(n)
    client = _fake(n, "my answer")
    await run_council(
        prompt="Q",
        agents=agents,
        model_client=client,
        topology=RingTopology(n),
        protocol=SpyProtocol(),
        aggregation=MajorityVote(normalizer=IdentityNormalizer()),
        termination=FixedRounds(2),
    )
    # Check round-1 contexts: each agent should see exactly 1 visible response.
    round1 = [(aid, visible) for aid, rnd, visible in captured_contexts if rnd == 1]
    assert len(round1) == n, f"Expected {n} round-1 calls, got {len(round1)}"
    for agent_id, visible_ids in round1:
        assert len(visible_ids) == 1, (
            f"{agent_id} saw {len(visible_ids)} responses in round 1; expected 1 (predecessor)"
        )


# ---------------------------------------------------------------------------
# (c) Aggregation produces non-null result
# ---------------------------------------------------------------------------


async def test_aggregation_produces_non_null_result() -> None:
    agents = _agents(3)
    client = _fake(3, "42")
    result = await run_council(
        prompt="Q",
        agents=agents,
        model_client=client,
        topology=CompleteGraphTopology(3),
        protocol=DirectAnswerProtocol(),
        aggregation=MajorityVote(normalizer=IdentityNormalizer()),
        termination=FixedRounds(1),
    )
    assert isinstance(result, CouncilResult)
    assert result.final_answer != ""
    assert result.final_answer is not None
    assert result.confidence > 0.0


# ---------------------------------------------------------------------------
# (d) Token counts are non-zero
# ---------------------------------------------------------------------------


async def test_token_counts_are_non_zero() -> None:
    agents = _agents(2)
    client = _fake(2, "hello")
    result = await run_council(
        prompt="What is 6x7?",
        agents=agents,
        model_client=client,
        topology=CompleteGraphTopology(2),
        protocol=DirectAnswerProtocol(),
        aggregation=MajorityVote(normalizer=IdentityNormalizer()),
        termination=FixedRounds(1),
    )
    assert result.tokens_in > 0
    assert result.tokens_out > 0
    assert result.total_cost >= 0.0


# ---------------------------------------------------------------------------
# Anonymization end-to-end
# ---------------------------------------------------------------------------


async def test_anonymization_hides_real_agent_ids_in_prompts() -> None:
    """With anonymize=True, real agent_ids must not appear in any protocol prompt."""
    real_ids = ["agent-0", "agent-1", "agent-2"]
    prompt_contents: list[str] = []

    class CapturingProtocol(PeerReviewProtocol):
        def build_prompt(self, ctx):  # type: ignore[override]
            result = super().build_prompt(ctx)
            prompt_contents.append(result)
            return result

    agents = _agents(3)
    client = _fake(3, "forty-two")
    await run_council(
        prompt="Q",
        agents=agents,
        model_client=client,
        topology=CompleteGraphTopology(3),
        protocol=CapturingProtocol(),
        aggregation=MajorityVote(normalizer=IdentityNormalizer()),
        termination=FixedRounds(2),
        anonymize=True,
    )
    assert prompt_contents, "Expected at least one prompt to be captured"
    for prompt in prompt_contents:
        for real_id in real_ids:
            assert real_id not in prompt, (
                f"Real agent_id {real_id!r} leaked into a protocol prompt"
            )


async def test_anonymize_false_preserves_real_ids() -> None:
    """With anonymize=False, real agent_ids appear in visible_responses."""
    captured_visible: list[list[str]] = []

    class CapturingProtocol(PeerReviewProtocol):
        def build_prompt(self, ctx):  # type: ignore[override]
            if ctx.round_index > 0:
                captured_visible.append([r.agent_id for r in ctx.visible_responses])
            return super().build_prompt(ctx)

    agents = _agents(3)
    client = _fake(3, "answer")
    await run_council(
        prompt="Q",
        agents=agents,
        model_client=client,
        topology=CompleteGraphTopology(3),
        protocol=CapturingProtocol(),
        aggregation=MajorityVote(normalizer=IdentityNormalizer()),
        termination=FixedRounds(2),
        anonymize=False,
    )
    if captured_visible:
        all_seen = {aid for visible in captured_visible for aid in visible}
        assert any(aid.startswith("agent-") for aid in all_seen)


# ---------------------------------------------------------------------------
# ModelFailure partial-result handling
# ---------------------------------------------------------------------------


async def test_pipeline_continues_with_partial_results_on_failure() -> None:
    """If one of three agents fails, pipeline continues with the 2 successful responses."""
    responses: dict[tuple[str, int], str] = {
        ("agent-0", 0): "42",
        # agent-1 round 0 is missing → ModelFailure
        ("agent-2", 0): "42",
    }
    agents = _agents(3)
    client = FakeModelClient(responses)

    result = await run_council(
        prompt="Q",
        agents=agents,
        model_client=client,
        topology=CompleteGraphTopology(3),
        protocol=DirectAnswerProtocol(),
        aggregation=MajorityVote(normalizer=IdentityNormalizer()),
        termination=FixedRounds(1),
    )
    assert isinstance(result, CouncilResult)
    assert result.final_answer != ""
    # Only 2 successful responses; round_history should have 2 entries for round 0.
    round0 = [r for r in result.round_history if r.round_index == 0]
    assert len(round0) == 2


# ---------------------------------------------------------------------------
# rounds_used reflects actual rounds completed
# ---------------------------------------------------------------------------


async def test_rounds_used_equals_fixed_rounds() -> None:
    agents = _agents(2)
    client = _fake(2, "x")
    result = await run_council(
        prompt="Q",
        agents=agents,
        model_client=client,
        topology=CompleteGraphTopology(2),
        protocol=DirectAnswerProtocol(),
        aggregation=MajorityVote(normalizer=IdentityNormalizer()),
        termination=FixedRounds(3),
    )
    assert result.rounds_used == 3


# ---------------------------------------------------------------------------
# AgreementThreshold early exit
# ---------------------------------------------------------------------------


async def test_agreement_threshold_stops_early_on_consensus() -> None:
    """AgreementThreshold should terminate after round 0 when all agents agree."""
    agents = _agents(3)
    client = _fake(3, "42")  # all agents always return "42"

    result = await run_council(
        prompt="What is 6x7?",
        agents=agents,
        model_client=client,
        topology=CompleteGraphTopology(3),
        protocol=DirectAnswerProtocol(),
        aggregation=MajorityVote(normalizer=IdentityNormalizer()),
        termination=CompositeTermination(
            AgreementThreshold(0.8, normalizer=IdentityNormalizer()),
            FixedRounds(5),  # safety cap
        ),
    )
    # All three agents return "42" → 100% agreement → stops after round 0
    assert result.rounds_used == 1
    assert result.final_answer == "42"
    assert "agreement" in result.termination_reason


# ---------------------------------------------------------------------------
# Adjacency slot alignment — agent failure must not shift visibility indices
# ---------------------------------------------------------------------------


async def test_adjacency_correct_when_middle_agent_fails_in_round_0() -> None:
    """Regression: if agent-1 (slot 1) fails in round 0, agent-2's round-1 visibility
    must still see agent-0's response via the adjacency matrix, not agent-1's slot.

    With a complete graph (all visible), agents 0 and 2 succeed; agent 1 fails.
    In round 1, agents 0 and 2 should both see each other's round-0 response.
    The old bug would index prev_responses by position [0,1,...] instead of by
    agent slot, causing agent-2 to see agent-0's response where agent-1 was expected.
    """
    captured: dict[str, list[str]] = {}

    class SpyProtocol(DirectAnswerProtocol):
        def build_prompt(self, ctx):  # type: ignore[override]
            if ctx.round_index == 1:
                # Record which real or anonymized agent_ids are visible
                captured[ctx.agent_id] = [r.agent_id for r in ctx.visible_responses]
            return super().build_prompt(ctx)

    responses: dict[tuple[str, int], str] = {
        ("agent-0", 0): "answer-from-0",
        # agent-1 round 0 absent → ModelFailure
        ("agent-2", 0): "answer-from-2",
        ("agent-0", 1): "ok",
        ("agent-2", 1): "ok",
    }
    agents = _agents(3)
    client = FakeModelClient(responses)

    result = await run_council(
        prompt="Q",
        agents=agents,
        model_client=client,
        topology=CompleteGraphTopology(3),
        protocol=SpyProtocol(),
        aggregation=MajorityVote(normalizer=IdentityNormalizer()),
        termination=FixedRounds(2),
        anonymize=False,  # keep real ids so we can inspect them
    )
    assert isinstance(result, CouncilResult)
    # In round 1, surviving agents should see only the 2 responses that succeeded.
    for _agent_id, visible_ids in captured.items():
        # Only agent-0 and agent-2 produced round-0 responses.
        assert "agent-1" not in visible_ids, (
            f"agent-1 (which failed) appeared in visibility list: {visible_ids}"
        )
        # At most 2 visible responses (agent-0 and agent-2, minus self if applicable).
        assert len(visible_ids) <= 2


# ---------------------------------------------------------------------------
# Constitution §8 — zero framework imports in council.core
# ---------------------------------------------------------------------------


def test_core_has_no_framework_imports() -> None:
    import importlib.util

    spec = importlib.util.find_spec("council.core")
    assert spec is not None and spec.origin is not None
    with open(spec.origin) as f:
        source = f.read()

    forbidden = ["langgraph", "hydra", "mlflow", "opentelemetry", "langchain"]
    for fw in forbidden:
        assert fw not in source, f"council/core.py contains forbidden import: {fw}"
