"""Gradual semantics — abstract base class.

A GradualSemantics maps a QBAF to per-argument strength scores. It is a pure
mathematical function: no I/O, no async, no hidden state. Concrete
implementations (DF-QuAD, Quadratic Energy, Euler-based, Strategic-Coupled)
ship in W2/PR3-PR5.

Required properties for every concrete subclass (verified in their test files):
  - Determinism: same input → same output (byte-equal across runs).
  - Monotonicity in base scores: increasing the base score of an unattacked
    argument cannot decrease its strength.
  - Walton-Krabbe canonical agreement: on the committed canonical 5-move
    trace, the strengths match the per-semantics golden values.

Trace-aware semantics (ADR-0013) override `prepare(trace)` to return a new
instance with updated trace-derived state. The default implementation is a
no-op (returns self), suitable for stateless semantics like DF-QuAD, QE, Ebs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from council.dialect.trace import Trace
from council.symbolic.argue.baf import QBAF


class GradualSemantics(ABC):
    """Map a QBAF to per-argument strengths and an extension."""

    @abstractmethod
    def evaluate(self, baf: QBAF) -> dict[str, float]:
        """Return strengths keyed by `Argument.arg_id`. Range: [0, 1]."""

    @abstractmethod
    def preferred_extension(self, baf: QBAF) -> frozenset[str]:
        """Return the preferred extension as a frozen set of arg_ids."""

    def prepare(self, trace: Trace) -> GradualSemantics:
        """Trace-aware refresh hook (ADR-0013). Default: no-op (returns self).

        Trace-aware semantics override this to return a new instance with
        updated trace-derived state. The aggregator calls `sem.prepare(trace)`
        before `sem.evaluate(baf)` so the returned instance evaluates against
        the same Trace that produced the BAF. Subclasses that override must
        return a fresh instance, never mutate self (semantics are values).
        """
        return self
