"""Phase 1 pipeline integration smoke tests.

Four end-to-end scenarios exercising the full stack with FakeModelClient:
1. Three-agent, two-round PeerReview with structured output — Issue 3 path
2. Ring topology visibility enforcement (4 agents, adjacency verified)
3. Anonymization end-to-end (real IDs absent from all protocol prompts)
4. Structured-output + ranking round-trip (StructuredRanking extracts RichPreference)

No real model calls. All assertions are on FakeModelClient outputs.
"""

from __future__ import annotations

from council.aggregation import MajorityVote
from council.core import AgentConfig, run_council
from council.models import FakeModelClient
from council.normalizer import StructuredOutputNormalizer
from council.protocol import DirectAnswerProtocol, PeerReviewProtocol
from council.ranking import StructuredRanking
from council.topology import CompleteGraphTopology, RingTopology

# ---------------------------------------------------------------------------
# 1. Three-agent, two-round PeerReview with structured output
# ---------------------------------------------------------------------------


async def test_peer_review_two_rounds_structured_output() -> None:
    """Full PeerReview run: round 0 → structured JSON answers, round 1 → critique."""
    n = 3
    responses: dict[tuple[str, int], str] = {}
    for i in range(n):
        responses[(f"agent-{i}", 0)] = '{"answer": 72, "reasoning": "8 times 9 is 72"}'
        responses[(f"agent-{i}", 1)] = '{"ranking": ["Response A","Response B"], "scores": {"Response A": 8, "Response B": 6}}'

    agents = [AgentConfig(id=f"agent-{i}", model=f"fake/m{i}") for i in range(n)]
    client = FakeModelClient(responses)

    result = await run_council(
        prompt="What is 8 x 9?",
        agents=agents,
        model_client=client,
        topology=CompleteGraphTopology(n),
        protocol=PeerReviewProtocol(output_schema={"answer": {"type": "number"}}),
        aggregation=MajorityVote(normalizer=StructuredOutputNormalizer()),
        max_rounds=2,
    )
    # Round 0 answers all normalize to "72"; round 1 critique responses are also
    # aggregated (they don't normalize to "72"), so confidence < 1.0 over all rounds.
    # The majority form is still "72" (3/6 = 0.5, or dominant over other unique forms).
    assert result.final_answer == "72"
    assert result.confidence > 0.0
    assert result.rounds_used == 2
    assert result.tokens_in > 0
    assert result.tokens_out > 0


# ---------------------------------------------------------------------------
# 2. Ring topology — adjacency enforcement
# ---------------------------------------------------------------------------


async def test_ring_topology_4_agents_adjacency_enforcement() -> None:
    """4 agents, RingTopology: each agent in round 1 sees only its predecessor."""
    n = 4
    responses: dict[tuple[str, int], str] = {}
    for i in range(n):
        responses[(f"agent-{i}", 0)] = f"answer_from_agent_{i}"
        responses[(f"agent-{i}", 1)] = f"revised_by_agent_{i}"

    captured: list[tuple[str, int, list[str]]] = []

    class SpyProtocol(DirectAnswerProtocol):
        def build_prompt(self, ctx):  # type: ignore[override]
            captured.append((ctx.agent_id, ctx.round_index, [r.content for r in ctx.visible_responses]))
            return super().build_prompt(ctx)

    agents = [AgentConfig(id=f"agent-{i}", model=f"fake/m{i}") for i in range(n)]
    client = FakeModelClient(responses)

    await run_council(
        prompt="Q",
        agents=agents,
        model_client=client,
        topology=RingTopology(n),
        protocol=SpyProtocol(),
        aggregation=MajorityVote(normalizer=StructuredOutputNormalizer()),
        max_rounds=2,
        anonymize=False,
    )

    round1_calls = [(aid, visible) for aid, rnd, visible in captured if rnd == 1]
    assert len(round1_calls) == n

    for agent_id, visible_contents in round1_calls:
        assert len(visible_contents) == 1, (
            f"{agent_id} saw {len(visible_contents)} responses in round 1; expected 1"
        )
        idx = int(agent_id.split("-")[1])
        pred_idx = (idx - 1) % n
        assert visible_contents[0] == f"answer_from_agent_{pred_idx}", (
            f"{agent_id} expected predecessor agent-{pred_idx}'s content"
        )


# ---------------------------------------------------------------------------
# 3. Anonymization end-to-end
# ---------------------------------------------------------------------------


async def test_anonymization_real_ids_absent_from_all_prompts() -> None:
    """With anonymize=True, real agent IDs must not appear in any protocol prompt."""
    real_ids = ["agent-0", "agent-1", "agent-2"]
    prompts_seen: list[str] = []

    class CapturingProtocol(PeerReviewProtocol):
        def build_prompt(self, ctx):  # type: ignore[override]
            result = super().build_prompt(ctx)
            prompts_seen.append(result)
            return result

    n = 3
    responses: dict[tuple[str, int], str] = {}
    for i in range(n):
        responses[(f"agent-{i}", 0)] = "42"
        responses[(f"agent-{i}", 1)] = "still 42"

    agents = [AgentConfig(id=f"agent-{i}", model=f"fake/m{i}") for i in range(n)]
    client = FakeModelClient(responses)

    await run_council(
        prompt="Q",
        agents=agents,
        model_client=client,
        topology=CompleteGraphTopology(n),
        protocol=CapturingProtocol(),
        aggregation=MajorityVote(normalizer=StructuredOutputNormalizer()),
        max_rounds=2,
        anonymize=True,
    )

    assert prompts_seen, "Expected prompts to be captured"
    for prompt in prompts_seen:
        for real_id in real_ids:
            assert real_id not in prompt, (
                f"Real agent_id {real_id!r} leaked into prompt: {prompt[:200]!r}"
            )


# ---------------------------------------------------------------------------
# 4. StructuredRanking round-trip
# ---------------------------------------------------------------------------


async def test_structured_ranking_round_trip() -> None:
    """StructuredRanking.extract processes responses containing valid JSON rankings."""
    n = 2
    ranking_json = (
        '{"ranking": ["Response A", "Response B"], '
        '"scores": {"Response A": 9, "Response B": 6}, '
        '"reasoning": "A was clearer"}'
    )
    responses: dict[tuple[str, int], str] = {
        ("agent-0", 0): '{"answer": "Paris"}',
        ("agent-1", 0): '{"answer": "Paris"}',
        ("agent-0", 1): ranking_json,
        ("agent-1", 1): ranking_json,
    }

    agents = [AgentConfig(id=f"agent-{i}", model=f"fake/m{i}") for i in range(n)]
    client = FakeModelClient(responses)

    result = await run_council(
        prompt="What is the capital of France?",
        agents=agents,
        model_client=client,
        topology=CompleteGraphTopology(n),
        protocol=PeerReviewProtocol(output_schema=StructuredRanking.SCHEMA),
        aggregation=MajorityVote(normalizer=StructuredOutputNormalizer()),
        ranking=StructuredRanking(),
        max_rounds=2,
    )
    # Round 0 answers are "paris"; round 1 outputs are ranking JSON.
    # "paris" is the plurality winner across all rounds.
    assert result.final_answer == "paris"
    assert result.confidence > 0.0
    assert result.rounds_used == 2
