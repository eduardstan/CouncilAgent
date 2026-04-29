"""CouncilPolicy — maps (prompt, budget) → CouncilGenome.

Skeleton for W5 QD integration. The genome is the unit of search in L5
and the unit of provenance in ProvenanceReceipt.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CouncilGenome:
    """Frozen genome describing a council configuration.

    Full spec lives in council/evolve/genome.py (W5). This skeleton
    captures the fields needed by the core pipeline.
    """

    members: tuple[str, ...] = ()
    max_rounds: int = 2
    topology_name: str = "CompleteGraphTopology"
    protocol_name: str = "DeliberationAutomaton"
    aggregator_name: str = "CopelandAggregator"
    monitors: tuple[str, ...] = ()


class CouncilPolicy:
    """Maps (prompt, budget) → CouncilGenome. Skeleton for W5 QD archive."""

    def select_genome(
        self,
        prompt: str,
        budget_usd: float = 1.0,
    ) -> CouncilGenome:
        return CouncilGenome()
