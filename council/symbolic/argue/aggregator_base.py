"""L2 argumentation — Aggregator ABC.

Single source of the L2 contract. Concrete aggregators live in
`council/symbolic/argue/aggregator.py` (W2/PR6):

  - ArgumentationAggregator — the headline aggregator (BAF + gradual semantics)
  - LastProposeFallbackAggregator — fallback for empty/degenerate BAFs;
    emits CopelandConfidence (the constitutionally-blessed ordinal fallback)

The signature `aggregate(trace, *, original_question)` is the D8 fix at the
type level: the trace is the only data input — no `responses: list[...]`
overload, no `round_history`, no `original_prompt`. The architecture rules
freeze this signature.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from council.dialect.trace import Trace
from council.symbolic.argue.aggregation_result import AggregationResult


class Aggregator(ABC):
    """L2 base. Trace is the only data input.

    Async because future calibrator hooks (W3) may await a per-domain
    privileged-knowledge fetch.
    """

    @abstractmethod
    async def aggregate(
        self, trace: Trace, *, original_question: str
    ) -> AggregationResult:
        """Aggregate the trace into a typed AggregationResult."""
