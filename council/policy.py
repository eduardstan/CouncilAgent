"""CouncilPolicy — map (prompt, TaskProfile, budget) → CouncilConfig.

Constitution §3: CouncilPolicy decides what to run; it does not run it.
It is the only place in the codebase that knows about task types, budget tiers,
and model selection simultaneously. Layer modules know nothing about policy.

The three default models are free-tier OpenRouter models — safe for fast
prototyping and integration testing without API cost.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from council.aggregation import Aggregation, MajorityVote, MetaJudge
from council.core import AgentConfig
from council.models import ModelClient
from council.protocol import DirectAnswerProtocol, PeerReviewProtocol, Protocol
from council.ranking import NullRanking, Ranking
from council.task_profile import TaskProfile
from council.termination import (
    AgreementThreshold,
    CompositeTermination,
    FixedRounds,
    TerminationStrategy,
)
from council.topology import CompleteGraphTopology, Topology

# Free-tier OpenRouter models — zero cost, usable without budget constraints.
_FREE_MODELS: list[str] = [
    "openrouter/google/gemma-3-27b-it:free",
    "openrouter/nvidia/nemotron-3-nano-30b-a3b:free",
    "openrouter/z-ai/glm-4.5-air:free",
]


@dataclass(frozen=True, slots=True)
class CouncilConfig:
    """Fully resolved configuration for one council run.

    Produced by CouncilPolicy.plan() and consumed by CouncilAgent.complete().
    Contains every parameter needed to call run_council() without further
    decision-making.
    """

    name: str
    agents: list[AgentConfig]
    topology: Topology
    protocol: Protocol
    aggregation: Aggregation
    termination: TerminationStrategy
    ranking: Ranking = field(default_factory=NullRanking)
    anonymize: bool = True
    estimated_cost_usd: float = 0.0
    answer_response_format: dict[str, object] | None = None
    prompt_hint: str = ""


class CouncilPolicy:
    """Map (prompt, TaskProfile, budget) → CouncilConfig.

    Builds two tiers for any TaskProfile:
    - fast_vote:              1 round, DirectAnswerProtocol, MajorityVote
    - standard_deliberation:  up to 2 rounds with agreement threshold,
                              PeerReviewProtocol, task-appropriate aggregation

    The most capable tier that fits within budget_usd is returned by plan().
    Free OpenRouter models have estimated_cost_usd == 0.0, so both tiers are
    always affordable when using the default model list.
    """

    def __init__(
        self,
        model_client: ModelClient,
        default_models: list[str] | None = None,
        budget_usd: float = 0.10,
        meta_judge_model: str | None = None,
    ) -> None:
        self._model_client = model_client
        self._models = default_models if default_models is not None else _FREE_MODELS
        self._budget = budget_usd
        # Explicit synthesis model for MetaJudge. Falls back to self._models[0]
        # so callers that don't need a dedicated judge model get sensible behaviour.
        self._meta_judge_model = meta_judge_model

    def plan(self, prompt: str, task_profile: TaskProfile) -> CouncilConfig:
        """Return the most capable affordable config for the given task profile."""
        tiers = self._build_tiers(task_profile)
        affordable = [t for t in tiers if t.estimated_cost_usd <= self._budget]
        if not affordable:
            return tiers[0]  # always return at least the cheapest option
        return affordable[-1]  # most capable within budget

    def _build_tiers(self, task_profile: TaskProfile) -> list[CouncilConfig]:
        agents = [
            AgentConfig(id=f"agent-{i}", model=model)
            for i, model in enumerate(self._models)
        ]
        n = len(agents)
        topology = CompleteGraphTopology(n)

        output_schema = task_profile.output_schema
        # When the task declares a structured output schema, request JSON from the
        # model on every answer round. None means free-text (no format enforcement).
        rf: dict[str, object] | None = {"type": "json_object"} if output_schema else None

        # Tier 1 — fast_vote: single round, majority vote regardless of task type.
        fast = CouncilConfig(
            name="fast_vote",
            agents=agents,
            topology=topology,
            protocol=DirectAnswerProtocol(output_schema=output_schema),
            aggregation=MajorityVote(normalizer=task_profile.normalizer),
            termination=FixedRounds(1),
            estimated_cost_usd=0.0,
            answer_response_format=rf,
            prompt_hint=task_profile.prompt_hint,
        )

        # Tier 2 — standard_deliberation: peer review, agreement-gated, task-aware agg.
        standard_protocol = PeerReviewProtocol(output_schema=output_schema)
        if task_profile.recommended_aggregation == "meta_judge":
            judge_model = self._meta_judge_model if self._meta_judge_model else self._models[0]
            # Label rounds via the protocol's own answer/critique predicate, so
            # MetaJudge stays protocol-agnostic while tracking phase correctly.
            def _round_label(round_index: int, _p: Protocol = standard_protocol) -> str:
                if round_index == 0:
                    return "GENERATE"
                return "ANSWER" if _p.is_answer_round(round_index) else "CRITIQUE"

            agg: Aggregation = MetaJudge(
                model=judge_model,
                model_client=self._model_client,
                round_label_fn=_round_label,
                response_format=rf,
                normalizer=task_profile.normalizer,
            )
        else:
            agg = MajorityVote(normalizer=task_profile.normalizer)

        standard = CouncilConfig(
            name="standard_deliberation",
            agents=agents,
            topology=topology,
            protocol=standard_protocol,
            aggregation=agg,
            termination=CompositeTermination(
                AgreementThreshold(0.8, normalizer=task_profile.normalizer),
                FixedRounds(2),
            ),
            estimated_cost_usd=0.0,
            answer_response_format=rf,
            prompt_hint=task_profile.prompt_hint,
        )

        return [fast, standard]
