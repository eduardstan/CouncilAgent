"""L2 — concrete Aggregator implementations.

Two aggregators ship in W2/PR6:

  - LastProposeFallbackAggregator: returns the last Propose's claim as
    the answer with `CopelandConfidence(0.5)` (Constitution §5 ordinal
    fallback). Used inside ArgumentationAggregator on empty/degenerate
    BAFs and as the W0/W1 default `CouncilContext.aggregator`.

  - ArgumentationAggregator: the headline L2 aggregator. Builds a QBAF
    via `build_qbaf(trace, calibrator)`, calls `semantics.prepare(trace)`
    (ADR-0013) for trace-aware semantics, evaluates strengths, picks
    the highest-strength Propose-derived Argument as the winner, and
    returns `BAFMarginConfidence` (winner_strength - runner_up_strength,
    clamped to [0, 1]).

Both aggregators implement the L2 contract from
`council/symbolic/argue/aggregator_base.py`:

    async def aggregate(self, trace, *, original_question) -> AggregationResult

Trace is the only data input -- D8 fix at the type level.
"""

from __future__ import annotations

from council.calibrate import Calibrator
from council.context import BAFMarginConfidence, CopelandConfidence
from council.dialect.moves import Propose
from council.dialect.trace import Trace
from council.symbolic.argue.aggregation_result import AggregationResult
from council.symbolic.argue.aggregator_base import Aggregator
from council.symbolic.argue.builders import build_qbaf
from council.symbolic.argue.semantics.base import GradualSemantics
from council.symbolic.argue.semantics.df_quad import DFQuADSemantics


class LastProposeFallbackAggregator(Aggregator):
    """Fallback aggregator: returns last Propose's claim with CopelandConfidence.

    Used as ArgumentationAggregator's default fallback on empty/degenerate
    BAFs and as the W0/W1 default CouncilContext.aggregator. The
    constitutional choice of CopelandConfidence (over plurality fraction)
    follows §5: only the four tagged Confidence subtypes are valid;
    plurality fraction is type-impossible.
    """

    async def aggregate(
        self, trace: Trace, *, original_question: str
    ) -> AggregationResult:
        proposes = [m for m in trace.moves if isinstance(m, Propose)]
        answer = proposes[-1].claim.surface if proposes else ""
        return AggregationResult(
            answer=answer,
            confidence=CopelandConfidence(value=0.5),
            method="LastProposeFallbackAggregator",
            metadata={"original_question": original_question},
        )


class ArgumentationAggregator(Aggregator):
    """Headline L2 aggregator — BAF + gradual semantics + BAFMarginConfidence.

    Args:
      semantics: the gradual semantics. Default DFQuADSemantics.
      calibrator: optional Calibrator threaded through to build_qbaf.
        Defaults to None (Propose.confidence used as base score).
      fallback: aggregator used when the QBAF has no Propose-derived
        arguments. Default LastProposeFallbackAggregator.
    """

    def __init__(
        self,
        semantics: GradualSemantics | None = None,
        calibrator: Calibrator | None = None,
        fallback: Aggregator | None = None,
    ) -> None:
        self._sem: GradualSemantics = semantics or DFQuADSemantics()
        self._calibrator = calibrator
        self._fallback: Aggregator = fallback or LastProposeFallbackAggregator()

    async def aggregate(
        self, trace: Trace, *, original_question: str
    ) -> AggregationResult:
        baf = build_qbaf(trace, calibrator=self._calibrator)

        # Filter to Propose-derived non-withdrawn arguments — these are the
        # only candidate winners. baf.proposals() returns all non-withdrawn
        # args (including Challenge / Concede-derived per ADR-0009); we
        # cross-reference with trace.moves to extract the Propose-derived
        # subset. The trace is the source of truth for argument provenance.
        propose_move_ids = {
            m.move_id for m in trace.moves if isinstance(m, Propose)
        }
        candidates = [
            a
            for a in baf.proposals()
            if a.arg_id in propose_move_ids
        ]
        if not candidates:
            # No Propose-derived candidates. Fall back.
            return await self._fallback.aggregate(
                trace, original_question=original_question
            )

        # ADR-0013: trace-aware semantics get a fresh prepare(trace) call.
        # Stateless semantics inherit the no-op default (returns self).
        sem = self._sem.prepare(trace)
        strengths = sem.evaluate(baf)
        extension = sem.preferred_extension(baf)

        winner = max(candidates, key=lambda a: strengths[a.arg_id])
        runner_ups = [a for a in candidates if a.arg_id != winner.arg_id]
        runner_up_strength = (
            max(strengths[a.arg_id] for a in runner_ups)
            if runner_ups
            else 0.0
        )
        margin = strengths[winner.arg_id] - runner_up_strength
        # Strengths are in [0, 1] and winner is by max, so margin is in [0, 1].
        # Clamp defensively against floating-point drift.
        margin_clamped = max(0.0, min(1.0, margin))

        return AggregationResult(
            answer=winner.claim_surface,
            confidence=BAFMarginConfidence(value=margin_clamped),
            method="ArgumentationAggregator",
            metadata={
                "qbaf": baf,
                "strengths": dict(strengths),
                "extension": extension,
                "original_question": original_question,
            },
        )
