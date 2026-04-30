"""L2 argumentation — AggregationResult value object.

The typed return value of every Aggregator. The confidence union is
intentionally narrower than CouncilResponse.confidence:

  - BAFMarginConfidence — produced by ArgumentationAggregator (the headline
    W2 type; Constitution §5).
  - CopelandConfidence — the constitutionally-blessed ordinal fallback used
    by LastProposeFallbackAggregator and any future ordinal-only aggregator.

JSDConfidence (L3) and MonitorVerdictConfidence (L1) are NOT valid aggregator
outputs — they are produced by their respective layers and reach
CouncilResponse via separate paths in agent.py / core.py.
"""

from __future__ import annotations

from dataclasses import dataclass

from council.context import BAFMarginConfidence, CopelandConfidence

#: Narrower than CouncilResponse.confidence — only L2-derivable types
#: plus the ordinal fallback. mypy --strict enforces this at compile time.
AggregatorConfidence = BAFMarginConfidence | CopelandConfidence


@dataclass(frozen=True, slots=True)
class AggregationResult:
    """Result of an Aggregator.aggregate(trace, original_question=...) call.

    Fields:
      answer: the chosen answer surface (the winning Propose's claim).
      confidence: BAF margin or Copeland-style ordinal fallback.
      method: the Aggregator subclass name (for provenance / logging).
      metadata: free-form bag for layer-specific extras. Headline keys
        used by ArgumentationAggregator (W2/PR6):
          - "baf_mermaid": str (live-render-ready Mermaid; demo gold)
          - "strengths": dict[str, float] (per-arg gradual semantics output)
          - "extension": frozenset[str] (preferred extension argument IDs)
        Other aggregators may use different keys; consumers must check.
    """

    answer: str
    confidence: AggregatorConfidence
    method: str
    metadata: dict[str, object]
