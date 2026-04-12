"""End-to-end integration tests for CouncilAgent with real free OpenRouter models.

Requires:
  - RUN_INTEGRATION=1 environment variable
  - OPENROUTER_API_KEY set in .env or environment

Run with:
  RUN_INTEGRATION=1 uv run pytest tests/integration/test_council_agent_e2e.py -v
"""

from __future__ import annotations

import pytest

from council.agent import CouncilAgent, HumanInTheLoop
from council.aggregation import MajorityVote
from council.context import AgentResponse
from council.core import AgentConfig
from council.models import LiteLLMClient
from council.normalizer import IdentityNormalizer, StructuredOutputNormalizer
from council.policy import CouncilConfig, CouncilPolicy, _FREE_MODELS
from council.protocol import DirectAnswerProtocol
from council.task_profile import TaskProfile
from council.termination import FixedRounds
from council.topology import CompleteGraphTopology

pytestmark = pytest.mark.integration

# The three free OpenRouter models used for all integration tests.
_MODELS = _FREE_MODELS


@pytest.fixture(scope="module")
def client() -> LiteLLMClient:
    return LiteLLMClient()


@pytest.fixture(scope="module")
def fast_config() -> CouncilConfig:
    agents = [AgentConfig(id=f"agent-{i}", model=m) for i, m in enumerate(_MODELS)]
    return CouncilConfig(
        name="fast_vote",
        agents=agents,
        topology=CompleteGraphTopology(len(agents)),
        protocol=DirectAnswerProtocol(),
        aggregation=MajorityVote(normalizer=StructuredOutputNormalizer()),
        termination=FixedRounds(1),
    )


# ---------------------------------------------------------------------------
# Smoke test — simple math
# ---------------------------------------------------------------------------


async def test_council_agent_complete_simple_math(
    client: LiteLLMClient, fast_config: CouncilConfig
) -> None:
    """All three free models answer '2+2'; council returns a response with content."""
    agent = CouncilAgent(config=fast_config, model_client=client)
    response = await agent.complete("What is 2+2? Reply with just the number.")

    assert isinstance(response, AgentResponse)
    assert response.content != "", "Expected a non-empty answer"
    assert "4" in response.content, f"Expected '4' in answer, got: {response.content!r}"
    assert response.agent_id == "council"
    assert response.metadata["rounds_used"] >= 1


# ---------------------------------------------------------------------------
# CouncilPolicy end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.timeout(180)
async def test_council_agent_complete_with_policy(client: LiteLLMClient) -> None:
    """CouncilPolicy.plan() + CouncilAgent.complete() returns a confident answer.

    Uses standard_deliberation tier (PeerReviewProtocol, up to 6 free-model calls).
    Free models can take 20-60s each — allowed up to 180s total.
    """
    task_profile = TaskProfile(
        name="factual",
        normalizer=StructuredOutputNormalizer(),
        recommended_aggregation="majority_vote",
    )
    policy = CouncilPolicy(model_client=client, budget_usd=0.10)
    config = policy.plan("What is the capital of France?", task_profile)
    agent = CouncilAgent(config=config, model_client=client)
    response = await agent.complete("What is the capital of France?")

    assert isinstance(response, AgentResponse)
    assert response.content != ""
    assert response.metadata["confidence"] > 0.0


# ---------------------------------------------------------------------------
# HumanInTheLoop escalation — ambiguous prompt
# ---------------------------------------------------------------------------


async def test_human_in_the_loop_on_ambiguous_prompt(client: LiteLLMClient) -> None:
    """On a prompt likely to cause disagreement, HumanInTheLoop may fire.

    This test sets a very high escalation threshold (0.99) so that unless all
    three models agree exactly, escalation is triggered.
    """
    agents = [AgentConfig(id=f"agent-{i}", model=m) for i, m in enumerate(_MODELS)]
    config = CouncilConfig(
        name="deliberation",
        agents=agents,
        topology=CompleteGraphTopology(len(agents)),
        protocol=DirectAnswerProtocol(),
        aggregation=MajorityVote(normalizer=IdentityNormalizer()),
        termination=FixedRounds(1),
    )
    agent = CouncilAgent(
        config=config,
        model_client=client,
        escalation=HumanInTheLoop(),
        escalation_threshold=0.99,  # almost always escalates
    )
    response = await agent.complete(
        "Describe your opinion on the most important challenge in AI alignment. "
        "Be brief (1-2 sentences)."
    )

    assert isinstance(response, AgentResponse)
    assert response.content != ""
    # With threshold 0.99 and open-ended question, escalation is highly likely.
    # We don't assert it must fire — models may occasionally agree — but we do
    # assert the response is valid either way.
    assert isinstance(response.metadata.get("needs_human_review"), bool)


# ---------------------------------------------------------------------------
# Cost is tracked
# ---------------------------------------------------------------------------


async def test_cost_is_tracked(client: LiteLLMClient, fast_config: CouncilConfig) -> None:
    """For free models, cost should be 0.0 or close to it."""
    agent = CouncilAgent(config=fast_config, model_client=client)
    response = await agent.complete("What is 1+1?")

    # Free models → cost is 0.0 from LiteLLM hidden_params
    assert response.cost >= 0.0
