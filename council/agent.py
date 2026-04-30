"""CouncilAgent — drop-in replacement for a single LLM call.

Same interface: complete(prompt) → CouncilResponse. Internally runs the
full council pipeline via run_council(). (Constitution §2)
"""

from __future__ import annotations

from council.context import CouncilContext, CouncilResponse
from council.core import run_council
from council.dialect.protocols.deliberation import DeliberationAutomaton
from council.models import ModelClient
from council.symbolic.argue.aggregator import ArgumentationAggregator
from council.symbolic.argue.aggregator_base import Aggregator
from council.symbolic.argue.semantics.df_quad import DFQuADSemantics
from council.termination import FixedRounds, TerminationStrategy
from council.topology import CompleteGraphTopology, Topology


def _default_aggregator() -> Aggregator:
    """Headline default for the user-facing CouncilAgent: ArgumentationAggregator
    with DFQuADSemantics. CouncilContext alone has no default (None) so that
    direct callers of run_council can opt into the W0/W1 LastProposeFallback
    behavior; CouncilAgent always wires up the L2 default."""
    return ArgumentationAggregator(semantics=DFQuADSemantics())


class CouncilAgent:
    """Drop-in replacement for a single LLM. complete(prompt) → CouncilResponse."""

    def __init__(
        self,
        agents: tuple[str, ...],
        model_client: ModelClient,
        *,
        topology: Topology | None = None,
        termination: TerminationStrategy | None = None,
        aggregator: Aggregator | None = None,
        anonymize: bool = True,
        max_rounds: int = 2,
    ) -> None:
        n = len(agents)
        self._context = CouncilContext(
            agents=agents,
            model_client=model_client,
            protocol=DeliberationAutomaton(max_phases=max_rounds, agents=list(agents)),
            topology=topology or CompleteGraphTopology(n_agents=n),
            termination=termination or FixedRounds(max_rounds=max_rounds),
            aggregator=aggregator or _default_aggregator(),
            anonymize=anonymize,
        )

    async def complete(self, prompt: str) -> CouncilResponse:
        """Run the council and return a CouncilResponse with ProvenanceReceipt."""
        return await run_council(prompt, context=self._context)
