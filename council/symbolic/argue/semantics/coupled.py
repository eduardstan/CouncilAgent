"""Strategic-Coupled gradual semantics — DF-QuAD ⊕ ATL coalition reasoning.

ADR-0012 records the design. The semantics wraps a base GradualSemantics
(default DFQuAD) and demotes consensus-reaching arguments that lack
agent-witnessed evidence per T3's CTLK invariant. T7 (master plan §10)
states this semantics satisfies the invariant on a small instance --
mechanised in tests/regressions/test_t7_coupled.py.

The wrapper composes cleanly with W3 (calibrators), W6 (ILP-mined
evidence rules), and the W7 demo.

Key behaviour:
  - On traces where every consensus-strength argument has evidence backing,
    reduces exactly to the underlying base semantics (backward-compatible).
  - On traces violating T3's invariant (consensus reached without evidence),
    demotes by `alpha` (default 0.5), which knocks the argument out of the
    preferred extension when alpha * strength < threshold.

The `evidence_backed: frozenset[str]` parameter is computed by the
aggregator (PR6) via `coupled_atl.evidence_backed_arg_ids(trace)` and
threaded into the constructor. This preserves the GradualSemantics ABC
signature `evaluate(baf) -> dict` -- the semantics never sees the Trace
directly.
"""

from __future__ import annotations

from council.dialect.trace import Trace
from council.symbolic.argue.baf import QBAF
from council.symbolic.argue.coupled_atl import evidence_backed_arg_ids
from council.symbolic.argue.semantics.base import GradualSemantics
from council.symbolic.argue.semantics.df_quad import DFQuADSemantics

_DEFAULT_ALPHA = 0.5
_DEFAULT_CONSENSUS_THRESHOLD = 0.5
_EXTENSION_THRESHOLD = 0.5


class StrategicCoupledSemantics(GradualSemantics):
    """Wrapper semantics that demotes consensus-reaching args without backing.

    Args:
      base: the underlying gradual semantics (default DFQuADSemantics).
      evidence_backed: the set of arg_ids that have at least one agent
        witness with non-empty evidence. Compute via
        coupled_atl.evidence_backed_arg_ids(trace) at the aggregator level.
        Defaults to empty -- safe but aggressively demotes everything.
      alpha: demotion factor in [0, 1]. Default 0.5; alpha=0 means hard
        rejection (zero out unbacked consensus args); alpha=1 disables
        demotion (reduces to base).
      consensus_threshold: minimum strength for an arg to be considered
        "consensus-reaching" and thus subject to evidence checking.
        Default 0.5.
    """

    def __init__(
        self,
        base: GradualSemantics | None = None,
        evidence_backed: frozenset[str] = frozenset(),
        alpha: float = _DEFAULT_ALPHA,
        consensus_threshold: float = _DEFAULT_CONSENSUS_THRESHOLD,
    ) -> None:
        self._base: GradualSemantics = base if base is not None else DFQuADSemantics()
        self._evidence_backed = evidence_backed
        self._alpha = alpha
        self._threshold = consensus_threshold

    def evaluate(self, baf: QBAF) -> dict[str, float]:
        base_strengths = self._base.evaluate(baf)
        adjusted: dict[str, float] = {}
        for arg_id, strength in base_strengths.items():
            if (
                strength >= self._threshold
                and arg_id not in self._evidence_backed
            ):
                adjusted[arg_id] = strength * self._alpha
            else:
                adjusted[arg_id] = strength
        return adjusted

    def preferred_extension(self, baf: QBAF) -> frozenset[str]:
        if not baf.arguments:
            return frozenset()
        strengths = self.evaluate(baf)
        return frozenset(
            a.arg_id
            for a in baf.arguments
            if not a.withdrawn and strengths[a.arg_id] >= _EXTENSION_THRESHOLD
        )

    def prepare(self, trace: Trace) -> GradualSemantics:
        """Trace-aware refresh hook (ADR-0013).

        Returns a new StrategicCoupledSemantics with evidence_backed
        recomputed from the given Trace via the inline ATL fragment.
        Base, alpha, and consensus_threshold are preserved.
        """
        return StrategicCoupledSemantics(
            base=self._base,
            evidence_backed=evidence_backed_arg_ids(trace),
            alpha=self._alpha,
            consensus_threshold=self._threshold,
        )
