"""Integration smoke test — GSM8K parity check.

Gated by @pytest.mark.integration and RUN_INTEGRATION=1 env var.
Requires real model credentials (OPENROUTER_API_KEY by default; see
.env.example). Never run in CI by default.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

#: Default smoke-test model. OpenRouter free tier (zero cost), good enough for
#: a single GSM8K problem. The .env.example documents this as a free-tier
#: option. Override via the GSM8K_PARITY_MODEL env var.
_DEFAULT_MODEL = os.environ.get(
    "GSM8K_PARITY_MODEL",
    "openrouter/google/gemma-3-27b-it:free",
)


def _required_api_key_for(model: str) -> str:
    """Return the env-var name LiteLLM expects for this model's provider."""
    if model.startswith("openrouter/"):
        return "OPENROUTER_API_KEY"
    if model.startswith("openai/"):
        return "OPENAI_API_KEY"
    if model.startswith("anthropic/"):
        return "ANTHROPIC_API_KEY"
    return ""


@pytest.fixture
def _require_integration() -> None:
    if not os.environ.get("RUN_INTEGRATION"):
        pytest.skip("set RUN_INTEGRATION=1 to run integration tests")
    key_name = _required_api_key_for(_DEFAULT_MODEL)
    if key_name and not os.environ.get(key_name):
        pytest.skip(
            f"set {key_name} (or override GSM8K_PARITY_MODEL with a model whose "
            f"key you have) to run this test. See .env.example.",
        )


@pytest.mark.asyncio
async def test_gsm8k_single_problem(_require_integration: None) -> None:
    """Council answers a simple GSM8K problem; checks the answer contains 18.

    Uses OpenRouter free-tier Gemma 3 27B IT by default; override via
    GSM8K_PARITY_MODEL env var to test a different provider.
    """
    from council.agent import CouncilAgent
    from council.context import CouncilResponse
    from council.models import LiteLLMClient
    from tasks.profiles import REGISTRY

    profile = REGISTRY["gsm8k"]
    assert profile.answer_format == "numeric"

    client = LiteLLMClient()
    agent = CouncilAgent(
        agents=(_DEFAULT_MODEL, _DEFAULT_MODEL),
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
