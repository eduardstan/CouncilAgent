"""Integration smoke test — GSM8K parity check.

Gated by @pytest.mark.integration and RUN_INTEGRATION=1 env var.
Requires real model credentials. Never run in CI by default.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def _require_integration() -> None:
    if not os.environ.get("RUN_INTEGRATION"):
        pytest.skip("set RUN_INTEGRATION=1 to run integration tests")


@pytest.mark.asyncio
async def test_gsm8k_single_problem(_require_integration: None) -> None:
    """Council answers a simple GSM8K problem; checks answer is numeric."""
    from council.agent import CouncilAgent
    from council.context import CouncilResponse
    from council.models import LiteLLMClient
    from tasks.profiles import REGISTRY

    profile = REGISTRY["gsm8k"]
    assert profile.answer_format == "numeric"

    client = LiteLLMClient()
    agent = CouncilAgent(
        agents=("openai/gpt-4o-mini", "openai/gpt-4o-mini"),
        model_client=client,
        max_rounds=1,
    )

    problem = (
        "Janet's ducks lay 16 eggs per day. She eats 3 for breakfast every morning "
        "and bakes muffins for her friends every day with 4. She sells the remainder "
        "at the farmers' market daily for $2 per fresh duck egg. How much in dollars "
        "does she make every day at the farmers' market?"
    )

    result = await agent.complete(problem)

    assert isinstance(result, CouncilResponse)
    assert result.answer.strip() != ""
    # The correct answer is 18
    assert "18" in result.answer
