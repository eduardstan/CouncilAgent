"""L2 argumentation aggregator — BAF/QBAF + gradual semantics. (W2)

W2/PR1 ships the type-level skeleton:
  - QBAF / Argument / Attack / Support — frozen value objects (`baf`)
  - AggregationResult — typed Aggregator return value (`aggregation_result`)
  - Aggregator ABC — single L2 contract (`aggregator_base`)
  - GradualSemantics ABC — strength-function contract (`semantics.base`)

W2/PR2 ships the deterministic builder:
  - build_qbaf(trace, calibrator=None) → QBAF (`builders`)

W2/PR3 ships DF-QuAD (the default gradual semantics):
  - DFQuADSemantics — Rago-Toni-Aurisicchio-Baroni KR 2016 (`semantics.df_quad`)

PR4-PR5 add Quadratic Energy, Euler-based, and Strategic-Coupled semantics.
The Calibrator ABC consumed by `build_qbaf` lives at `council.calibrate.base`
(ADR-0008).
"""

from council.symbolic.argue.aggregation_result import (
    AggregationResult,
    AggregatorConfidence,
)
from council.symbolic.argue.aggregator_base import Aggregator
from council.symbolic.argue.baf import QBAF, Argument, Attack, Support
from council.symbolic.argue.builders import build_qbaf
from council.symbolic.argue.semantics.base import GradualSemantics
from council.symbolic.argue.semantics.df_quad import DFQuADSemantics

__all__ = [
    "QBAF",
    "AggregationResult",
    "Aggregator",
    "AggregatorConfidence",
    "Argument",
    "Attack",
    "DFQuADSemantics",
    "GradualSemantics",
    "Support",
    "build_qbaf",
]
