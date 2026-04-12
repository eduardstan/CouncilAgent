"""CouncilPolicy — map (prompt, TaskProfile, budget) → CouncilConfig.

Constitution §3: CouncilPolicy decides what to run; it does not run it.
It is the only place in the codebase that knows about task types, budget tiers,
and model selection simultaneously. Layer modules know nothing about policy.

The three default models are free-tier OpenRouter models — safe for fast
prototyping and integration testing without API cost.
"""

from __future__ import annotations

from dataclasses import dataclass

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
# Using the same model three times provides diversity via temperature sampling
# when peer alternatives are unavailable or rate-limited. Replace with
# three distinct working models as availability stabilises.
_FREE_MODELS: list[str] = [
    "openrouter/google/gemma-3-27b-it:free",
    "openrouter/google/gemma-3-27b-it:free",
    "openrouter/google/gemma-3-27b-it:free",
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
    ranking: Ranking | None = None
    anonymize: bool = True
    estimated_cost_usd: float = 0.0


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
    ) -> None:
        self._model_client = model_client
        self._models = default_models if default_models is not None else _FREE_MODELS
        self._budget = budget_usd

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

        # Tier 1 — fast_vote: single round, majority vote regardless of task type.
        fast = CouncilConfig(
            name="fast_vote",
            agents=agents,
            topology=topology,
            protocol=DirectAnswerProtocol(),
            aggregation=MajorityVote(normalizer=task_profile.normalizer),
            termination=FixedRounds(1),
            estimated_cost_usd=0.0,
        )

        # Tier 2 — standard_deliberation: peer review, agreement-gated, task-aware agg.
        if task_profile.recommended_aggregation == "meta_judge":
            agg: Aggregation = MetaJudge(
                model=self._models[0],
                model_client=self._model_client,
            )
        else:
            agg = MajorityVote(normalizer=task_profile.normalizer)

        standard = CouncilConfig(
            name="standard_deliberation",
            agents=agents,
            topology=topology,
            protocol=PeerReviewProtocol(),
            aggregation=agg,
            termination=CompositeTermination(
                AgreementThreshold(0.8, normalizer=task_profile.normalizer),
                FixedRounds(2),
            ),
            estimated_cost_usd=0.0,
        )

        return [fast, standard]
