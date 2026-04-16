"""CouncilAgent — drop-in replacement for a single LLM call.

Constitution §1: the council is an agent, not a benchmark.
Constitution §2: complete(prompt) → AgentResponse, same shape as ModelClient.complete().

Extra fields (confidence, agreement_ratio, dissenting_views, rounds_used, method,
needs_human_review) are stored in AgentResponse.metadata so callers that only
read .content work without any changes.

Constitution §8: no framework imports (langgraph, hydra, mlflow, opentelemetry).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from council.context import AgentResponse, CouncilResult
from council.core import run_council
from council.models import ModelClient
from council.policy import CouncilConfig
from council.task_profile import TaskProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EscalationStrategy hierarchy
# ---------------------------------------------------------------------------


class EscalationStrategy(ABC):
    """Triggered when CouncilAgent.complete() produces low confidence."""

    @abstractmethod
    async def escalate(self, prompt: str, response: AgentResponse) -> AgentResponse: ...


class HumanInTheLoop(EscalationStrategy):
    """Flag the response for human review without re-running the pipeline."""

    async def escalate(self, prompt: str, response: AgentResponse) -> AgentResponse:
        return AgentResponse(
            agent_id=response.agent_id,
            content=response.content,
            round_index=response.round_index,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost=response.cost,
            metadata={**response.metadata, "needs_human_review": True},
        )


class UpgradeModels(EscalationStrategy):
    """Re-run the prompt with a stronger model list."""

    def __init__(
        self,
        upgraded_models: list[str],
        model_client: ModelClient,
        config: CouncilConfig,
    ) -> None:
        self._upgraded_models = upgraded_models
        self._model_client = model_client
        self._config = config

    async def escalate(self, prompt: str, response: AgentResponse) -> AgentResponse:
        from council.core import AgentConfig

        agents = [
            AgentConfig(id=f"agent-{i}", model=m)
            for i, m in enumerate(self._upgraded_models)
        ]
        result = await run_council(
            prompt=prompt,
            agents=agents,
            model_client=self._model_client,
            topology=self._config.topology,
            protocol=self._config.protocol,
            aggregation=self._config.aggregation,
            termination=self._config.termination,
            ranking=self._config.ranking,
            anonymize=self._config.anonymize,
        )
        return _result_to_response(result, base_cost=response.cost, escalated=True)


class AddDeliberation(EscalationStrategy):
    """Re-run with one additional deliberation round using the same model list."""

    def __init__(
        self,
        extra_rounds: int,
        model_client: ModelClient,
        config: CouncilConfig,
    ) -> None:
        self._extra_rounds = extra_rounds
        self._model_client = model_client
        self._config = config

    async def escalate(self, prompt: str, response: AgentResponse) -> AgentResponse:
        from council.termination import FixedRounds

        result = await run_council(
            prompt=prompt,
            agents=self._config.agents,
            model_client=self._model_client,
            topology=self._config.topology,
            protocol=self._config.protocol,
            aggregation=self._config.aggregation,
            termination=FixedRounds(self._extra_rounds + 1),
            ranking=self._config.ranking,
            anonymize=self._config.anonymize,
        )
        return _result_to_response(result, base_cost=response.cost, escalated=True)


# ---------------------------------------------------------------------------
# CouncilAgent
# ---------------------------------------------------------------------------


class CouncilAgent:
    """Drop-in LLM replacement — wraps run_council() behind complete(prompt).

    Returns AgentResponse (same type as ModelClient.complete()) so callers
    work without changes. Confidence and council metadata live in .metadata.

    Escalation fires when confidence < escalation_threshold. Default strategy
    is None (no escalation). Pass a HumanInTheLoop, UpgradeModels, or
    AddDeliberation instance to enable it.
    """

    def __init__(
        self,
        config: CouncilConfig,
        model_client: ModelClient,
        escalation: EscalationStrategy | None = None,
        escalation_threshold: float = 0.4,
    ) -> None:
        self._config = config
        self._model_client = model_client
        self._escalation = escalation
        self._escalation_threshold = escalation_threshold

    async def complete(
        self,
        prompt: str,
        task_profile: TaskProfile | None = None,
    ) -> AgentResponse:
        """Run the council and return an AgentResponse with council metadata."""
        result = await run_council(
            prompt=prompt,
            agents=self._config.agents,
            model_client=self._model_client,
            topology=self._config.topology,
            protocol=self._config.protocol,
            aggregation=self._config.aggregation,
            termination=self._config.termination,
            ranking=self._config.ranking,
            anonymize=self._config.anonymize,
            answer_response_format=self._config.answer_response_format,
        )

        response = _result_to_response(result)

        if self._escalation and result.confidence < self._escalation_threshold:
            logger.debug(
                "CouncilAgent: confidence %.2f < threshold %.2f — escalating",
                result.confidence,
                self._escalation_threshold,
            )
            response = await self._escalation.escalate(prompt, response)

        return response


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _result_to_response(
    result: CouncilResult,
    *,
    base_cost: float = 0.0,
    escalated: bool = False,
) -> AgentResponse:
    """Convert a CouncilResult to an AgentResponse (Constitution §2)."""
    last_round = result.rounds_used - 1
    last_responses = [r for r in result.round_history if r.round_index == last_round]
    winner = result.final_answer
    # NOTE: winner is already a canonical form (lowercased, stripped) produced by
    # the aggregation normalizer. Comparing via strip().lower() is approximate —
    # responses like "The answer is 72." won't match canonical "72" even though they
    # normalize to the same answer. This is informational metadata only; the final
    # answer and confidence are unaffected.
    dissenting = [r.content for r in last_responses if r.content.strip().lower() != winner]

    return AgentResponse(
        agent_id="council" if not escalated else "council-escalated",
        content=result.final_answer,
        round_index=last_round,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost=base_cost + result.total_cost,
        metadata={
            "confidence": result.confidence,
            "agreement_ratio": result.confidence,
            "dissenting_views": dissenting,
            "rounds_used": result.rounds_used,
            "method": result.method,
            "needs_human_review": False,
            "escalated": escalated,
        },
    )
