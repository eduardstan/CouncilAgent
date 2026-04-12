"""Tests for council/agent.py — CouncilAgent and EscalationStrategy hierarchy."""

from __future__ import annotations

import pytest

from council.agent import AddDeliberation, CouncilAgent, HumanInTheLoop, UpgradeModels
from council.aggregation import MajorityVote
from council.context import AgentResponse
from council.core import AgentConfig
from council.models import FakeModelClient
from council.normalizer import IdentityNormalizer
from council.policy import CouncilConfig
from council.protocol import DirectAnswerProtocol
from council.termination import FixedRounds
from council.topology import CompleteGraphTopology


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(n: int = 3, rounds: int = 1) -> CouncilConfig:
    agents = [AgentConfig(id=f"agent-{i}", model=f"fake/m-{i}") for i in range(n)]
    return CouncilConfig(
        name="test",
        agents=agents,
        topology=CompleteGraphTopology(n),
        protocol=DirectAnswerProtocol(),
        aggregation=MajorityVote(normalizer=IdentityNormalizer()),
        termination=FixedRounds(rounds),
    )


def _fake(n: int, answer: str = "42", rounds: int = 1) -> FakeModelClient:
    responses: dict[tuple[str, int], str] = {}
    for i in range(n):
        for r in range(rounds + 1):
            responses[(f"agent-{i}", r)] = answer
    return FakeModelClient(responses)


# ---------------------------------------------------------------------------
# CouncilAgent.complete()
# ---------------------------------------------------------------------------


class TestCouncilAgent:
    async def test_complete_returns_agent_response(self) -> None:
        agent = CouncilAgent(config=_config(), model_client=_fake(3))
        response = await agent.complete("What is 2+2?")
        assert isinstance(response, AgentResponse)

    async def test_content_is_final_answer(self) -> None:
        agent = CouncilAgent(config=_config(), model_client=_fake(3, "4"))
        response = await agent.complete("What is 2+2?")
        assert response.content == "4"

    async def test_agent_id_is_council(self) -> None:
        agent = CouncilAgent(config=_config(), model_client=_fake(3))
        response = await agent.complete("Q")
        assert response.agent_id == "council"

    async def test_metadata_has_confidence(self) -> None:
        agent = CouncilAgent(config=_config(), model_client=_fake(3, "42"))
        response = await agent.complete("Q")
        assert "confidence" in response.metadata
        assert response.metadata["confidence"] == pytest.approx(1.0)

    async def test_metadata_has_agreement_ratio(self) -> None:
        agent = CouncilAgent(config=_config(), model_client=_fake(3, "42"))
        response = await agent.complete("Q")
        assert "agreement_ratio" in response.metadata

    async def test_metadata_has_rounds_used(self) -> None:
        agent = CouncilAgent(config=_config(rounds=1), model_client=_fake(3))
        response = await agent.complete("Q")
        assert response.metadata["rounds_used"] == 1

    async def test_metadata_has_method(self) -> None:
        agent = CouncilAgent(config=_config(), model_client=_fake(3))
        response = await agent.complete("Q")
        assert "method" in response.metadata
        assert response.metadata["method"] == "MajorityVote"

    async def test_metadata_has_dissenting_views(self) -> None:
        agent = CouncilAgent(config=_config(), model_client=_fake(3))
        response = await agent.complete("Q")
        assert "dissenting_views" in response.metadata

    async def test_dissenting_views_when_minority_disagrees(self) -> None:
        # 2 agents say "yes", 1 says "no" → "no" is a dissenting view.
        responses = {
            ("agent-0", 0): "yes",
            ("agent-1", 0): "yes",
            ("agent-2", 0): "no",
        }
        agent = CouncilAgent(config=_config(3), model_client=FakeModelClient(responses))
        response = await agent.complete("Q")
        assert response.content == "yes"
        assert "no" in response.metadata["dissenting_views"]

    async def test_needs_human_review_false_by_default(self) -> None:
        agent = CouncilAgent(config=_config(), model_client=_fake(3))
        response = await agent.complete("Q")
        assert response.metadata["needs_human_review"] is False

    async def test_cost_is_accumulated(self) -> None:
        agent = CouncilAgent(config=_config(), model_client=_fake(3))
        response = await agent.complete("Q")
        assert response.cost >= 0.0

    async def test_tokens_are_non_zero(self) -> None:
        agent = CouncilAgent(config=_config(), model_client=_fake(3))
        response = await agent.complete("Q")
        assert response.tokens_in > 0
        assert response.tokens_out > 0


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------


class TestHumanInTheLoop:
    async def test_sets_needs_human_review(self) -> None:
        strategy = HumanInTheLoop()
        original = AgentResponse(
            agent_id="council", content="maybe", round_index=0,
            tokens_in=1, tokens_out=1, cost=0.0,
            metadata={"confidence": 0.3, "needs_human_review": False},
        )
        escalated = await strategy.escalate("Q", original)
        assert escalated.metadata["needs_human_review"] is True

    async def test_preserves_content_and_cost(self) -> None:
        strategy = HumanInTheLoop()
        original = AgentResponse(
            agent_id="council", content="uncertain answer", round_index=0,
            tokens_in=5, tokens_out=3, cost=0.01,
            metadata={"confidence": 0.2, "needs_human_review": False},
        )
        escalated = await strategy.escalate("Q", original)
        assert escalated.content == "uncertain answer"
        assert escalated.cost == pytest.approx(0.01)


class TestCouncilAgentEscalation:
    async def test_human_in_the_loop_fires_on_low_confidence(self) -> None:
        # All agents disagree → confidence = 1/3 < threshold 0.4.
        responses = {
            ("agent-0", 0): "A",
            ("agent-1", 0): "B",
            ("agent-2", 0): "C",
        }
        agent = CouncilAgent(
            config=_config(3),
            model_client=FakeModelClient(responses),
            escalation=HumanInTheLoop(),
            escalation_threshold=0.5,
        )
        response = await agent.complete("Q")
        assert response.metadata["needs_human_review"] is True

    async def test_no_escalation_when_confidence_above_threshold(self) -> None:
        # All agree → confidence = 1.0, no escalation.
        agent = CouncilAgent(
            config=_config(3),
            model_client=_fake(3, "42"),
            escalation=HumanInTheLoop(),
            escalation_threshold=0.5,
        )
        response = await agent.complete("Q")
        assert response.metadata["needs_human_review"] is False

    async def test_upgrade_models_uses_different_agents(self) -> None:
        upgraded = ["fake/strong-0", "fake/strong-1", "fake/strong-2"]
        responses: dict[tuple[str, int], str] = {}
        for i in range(3):
            responses[(f"agent-{i}", 0)] = chr(65 + i)  # A, B, C → low confidence
        for i in range(3):
            responses[(f"agent-{i}", 0)] = "strong-answer"  # same keys — checked below

        # Provide responses for upgraded agent IDs.
        upgraded_responses = {(f"agent-{i}", 0): "strong-answer" for i in range(3)}
        # All-disagreement client for initial run; upgraded client for escalation.
        initial_client = FakeModelClient({
            ("agent-0", 0): "A", ("agent-1", 0): "B", ("agent-2", 0): "C",
        })
        upgrade_client = FakeModelClient(upgraded_responses)

        strategy = UpgradeModels(
            upgraded_models=upgraded,
            model_client=upgrade_client,
            config=_config(3),
        )
        agent = CouncilAgent(
            config=_config(3),
            model_client=initial_client,
            escalation=strategy,
            escalation_threshold=0.5,
        )
        response = await agent.complete("Q")
        assert response.content == "strong-answer"
        assert response.agent_id == "council-escalated"


# ---------------------------------------------------------------------------
# Constitution §8 — no framework imports in council.agent
# ---------------------------------------------------------------------------


def test_agent_has_no_framework_imports() -> None:
    import importlib.util

    spec = importlib.util.find_spec("council.agent")
    assert spec is not None and spec.origin is not None
    with open(spec.origin) as f:
        source = f.read()

    # Check import lines only — the words may appear in docstrings/comments.
    import_lines = [
        line for line in source.splitlines()
        if line.strip().startswith(("import ", "from ")) and not line.strip().startswith("#")
    ]
    import_text = "\n".join(import_lines)

    forbidden = ["langgraph", "hydra", "mlflow", "opentelemetry", "langchain"]
    for fw in forbidden:
        assert fw not in import_text, f"council/agent.py imports forbidden framework: {fw}"
