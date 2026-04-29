"""CouncilAgent — drop-in replacement for a single LLM call.

Same interface: complete(prompt) → CouncilResponse. Internally runs the
full council pipeline via run_council(). (Constitution §2)
"""

from __future__ import annotations

from council.context import CouncilContext, CouncilResponse
from council.core import run_council
from council.dialect.protocols.deliberation import DeliberationAutomaton
from council.models import ModelClient
from council.termination import FixedRounds, TerminationStrategy
from council.topology import CompleteGraphTopology, Topology


class CouncilAgent:
    """Drop-in replacement for a single LLM. complete(prompt) → CouncilResponse."""

    def __init__(
        self,
        agents: tuple[str, ...],
        model_client: ModelClient,
        *,
        topology: Topology | None = None,
        termination: TerminationStrategy | None = None,
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
            anonymize=anonymize,
        )

    async def complete(self, prompt: str) -> CouncilResponse:
        """Run the council and return a CouncilResponse with ProvenanceReceipt."""
        return await run_council(prompt, context=self._context)
