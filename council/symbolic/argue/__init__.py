"""L2 argumentation aggregator — BAF/QBAF + gradual semantics. (W2)

W2/PR1 ships the type-level skeleton:
  - QBAF / Argument / Attack / Support — frozen value objects (`baf`)
  - AggregationResult — typed Aggregator return value (`aggregation_result`)
  - Aggregator ABC — single L2 contract (`aggregator_base`)
  - GradualSemantics ABC — strength-function contract (`semantics.base`)

Concrete builders, semantics, aggregators, and visualisers ship in
W2/PR2-PR9. The Calibrator ABC consumed by `build_qbaf` lives at
`council.calibrate.base` (ADR-0008).
"""

from council.symbolic.argue.aggregation_result import (
    AggregationResult,
    AggregatorConfidence,
)
from council.symbolic.argue.aggregator_base import Aggregator
from council.symbolic.argue.baf import QBAF, Argument, Attack, Support
from council.symbolic.argue.semantics.base import GradualSemantics

__all__ = [
    "QBAF",
    "AggregationResult",
    "Aggregator",
    "AggregatorConfidence",
    "Argument",
    "Attack",
    "GradualSemantics",
    "Support",
]
