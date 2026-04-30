"""L2 argumentation — deterministic Trace → QBAF builder.

`build_qbaf(trace, calibrator=None)` is the canonical W2 construction. Pure
function: no model calls, no async, no mutation of the trace.

Construction rules from `COUNCIL_NS_PLAN.md §6.3`:
  - Every Propose → an argument node. Argument.arg_id == Propose.move_id;
    base_score = calibrator(propose.confidence, agent_id, claim.domain) when
    calibrator is given, else propose.confidence.
  - Every Challenge(target, reason) → attack edge (Slice C; PR2/Slice C).
  - Every Concede(target) → support edge (Slice C; PR2/Slice C).
  - Every Retract(own) → mark argument withdrawn (Slice C; PR2/Slice C).
  - Every Vote(option, conf) → base-score boost on the matching Propose's
    argument (clamped to [0, 1]).
  - Self-attack detection (claim.domain ∈ {ARITH, FOL}) is deferred to PR8
    behind the [argue-asp] extra (ADR-0007). build_qbaf returns no
    self-attacks until then.

Vote-to-Propose matching is by exact `Vote.option.surface ==
Propose.claim.surface` equality. Surface normalisation is intentionally NOT
applied here — it lives at higher layers (W3 calibration, surface.py
rendering). Exact-equality matching is the strictest deterministic baseline.

Vote-boost rule: `base_score = calibrated_propose_score + sum(vote.confidence
for matching votes)`, clamped to [0, 1]. Aggressive but simple — saturating
sum, parallel to bible §6.3's literal "(clamped to [0, 1])" hint. Each vote
contributes its full confidence.
"""

from __future__ import annotations

from council.calibrate import Calibrator
from council.dialect.moves import Propose, Vote
from council.dialect.trace import Trace
from council.symbolic.argue.baf import QBAF, Argument


def build_qbaf(trace: Trace, calibrator: Calibrator | None = None) -> QBAF:
    """Construct a QBAF from a typed Trace. See module docstring for rules."""
    proposes: list[Propose] = []
    votes: list[Vote] = []
    for move in trace.moves:
        if isinstance(move, Propose):
            proposes.append(move)
        elif isinstance(move, Vote):
            votes.append(move)

    arguments: list[Argument] = []
    for prop in proposes:
        if calibrator is None:
            base = prop.confidence
        else:
            base = calibrator.calibrate(
                prop.confidence, prop.agent_id, prop.claim.domain
            )

        # Vote → boost: sum confidences of votes whose option.surface
        # matches this Propose's claim.surface.
        boost = sum(v.confidence for v in votes if v.option.surface == prop.claim.surface)
        score = max(0.0, min(1.0, base + boost))

        arguments.append(
            Argument(
                arg_id=prop.move_id,
                claim_surface=prop.claim.surface,
                base_score=score,
                withdrawn=False,
            )
        )

    return QBAF(arguments=tuple(arguments), attacks=(), supports=())
