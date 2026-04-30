"""L2 argumentation — deterministic Trace → QBAF builder.

`build_qbaf(trace, calibrator=None)` is the canonical W2 construction. Pure
function: no model calls, no async, no mutation of the trace.

Construction rules from `COUNCIL_NS_PLAN.md §6.3` (operationally adjusted
per ADR-0009 to keep edge sources structurally valid):

  - Every Propose → an Argument with `arg_id == Propose.move_id`.
    Base score = calibrator(propose.confidence, agent_id, claim.domain) when
    calibrator is given, else propose.confidence.
  - Every Challenge(target, reason, confidence) where `target` matches a
    known arg_id → an Argument (id = Challenge.move_id, surface =
    reason.surface, base_score = Challenge.confidence) plus an Attack edge
    (source = Challenge.move_id, target = Challenge.target, weight =
    Challenge.confidence).
  - Every Concede(target) where `target` matches a known arg_id → an
    Argument (id = Concede.move_id, surface = "(concession to {target})",
    base_score = 1.0) plus a Support edge (source = Concede.move_id, target
    = Concede.target, weight = 1.0).
  - Every Retract(own) where `own` matches a known arg_id → mark that
    Argument's `withdrawn=True`. No new node, no new edge.
  - Every Vote(option, conf) → base-score boost on Propose-derived
    arguments whose `claim_surface == option.surface` (saturating sum,
    clamped to [0, 1]).
  - Self-attack detection (claim.domain ∈ {ARITH, FOL}) is deferred to PR8
    behind the [argue-asp] extra (ADR-0007). build_qbaf returns no
    self-attacks until then.

Algorithm: single forward pass over `trace.moves` (so challenge-of-a-
challenge chains form naturally), then a vote-boost pass over the
Propose-derived records, then materialise frozen Arguments preserving
insertion order.

Vote-to-Propose matching is by exact `Vote.option.surface ==
Propose.claim.surface` equality. Surface normalisation lives at higher
layers (W3 calibration, surface.py rendering).

Moves whose target/own does not reference a known arg_id are dropped
silently (logged at DEBUG). The QBAF.__post_init__ no-dangling-edges
invariant guarantees this is the only structurally valid choice.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from council.calibrate import Calibrator
from council.dialect.moves import Challenge, Concede, Propose, Retract, Vote
from council.dialect.trace import Trace
from council.symbolic.argue.baf import QBAF, Argument, Attack, Support

logger = logging.getLogger(__name__)


@dataclass
class _ArgRecord:
    """Internal mutable record used during the forward pass."""

    arg_id: str
    surface: str
    base_score: float
    kind: str  # "propose" | "challenge" | "concede" — only "propose" gets vote boosts


@dataclass
class _BuildState:
    arg_ids: set[str] = field(default_factory=set)
    records: list[_ArgRecord] = field(default_factory=list)
    attacks: list[Attack] = field(default_factory=list)
    supports: list[Support] = field(default_factory=list)
    withdrawn: set[str] = field(default_factory=set)


def build_qbaf(trace: Trace, calibrator: Calibrator | None = None) -> QBAF:
    """Construct a QBAF from a typed Trace. See module docstring for rules."""
    state = _BuildState()
    votes: list[Vote] = []

    for move in trace.moves:
        match move:
            case Propose():
                _add_propose(move, state, calibrator)
            case Challenge():
                _add_challenge(move, state)
            case Concede():
                _add_concede(move, state)
            case Retract():
                _mark_retract(move, state)
            case Vote():
                votes.append(move)
            case _:
                pass  # Question, Clarify, Abstain, Pass — irrelevant to QBAF

    _apply_vote_boosts(state, votes)

    arguments = tuple(
        Argument(
            arg_id=r.arg_id,
            claim_surface=r.surface,
            base_score=r.base_score,
            withdrawn=r.arg_id in state.withdrawn,
        )
        for r in state.records
    )
    return QBAF(
        arguments=arguments,
        attacks=tuple(state.attacks),
        supports=tuple(state.supports),
    )


def _add_propose(
    move: Propose, state: _BuildState, calibrator: Calibrator | None
) -> None:
    if calibrator is None:
        base = move.confidence
    else:
        base = calibrator.calibrate(move.confidence, move.agent_id, move.claim.domain)
    state.records.append(
        _ArgRecord(
            arg_id=move.move_id,
            surface=move.claim.surface,
            base_score=base,
            kind="propose",
        )
    )
    state.arg_ids.add(move.move_id)


def _add_challenge(move: Challenge, state: _BuildState) -> None:
    if move.target not in state.arg_ids:
        logger.debug("dropping Challenge %s: unknown target %r", move.move_id, move.target)
        return
    state.records.append(
        _ArgRecord(
            arg_id=move.move_id,
            surface=move.reason.surface,
            base_score=move.confidence,
            kind="challenge",
        )
    )
    state.arg_ids.add(move.move_id)
    state.attacks.append(
        Attack(source=move.move_id, target=move.target, weight=move.confidence)
    )


def _add_concede(move: Concede, state: _BuildState) -> None:
    if move.target not in state.arg_ids:
        logger.debug("dropping Concede %s: unknown target %r", move.move_id, move.target)
        return
    state.records.append(
        _ArgRecord(
            arg_id=move.move_id,
            surface=f"(concession to {move.target})",
            base_score=1.0,
            kind="concede",
        )
    )
    state.arg_ids.add(move.move_id)
    state.supports.append(
        Support(source=move.move_id, target=move.target, weight=1.0)
    )


def _mark_retract(move: Retract, state: _BuildState) -> None:
    if move.own not in state.arg_ids:
        logger.debug("dropping Retract %s: unknown own %r", move.move_id, move.own)
        return
    state.withdrawn.add(move.own)


def _apply_vote_boosts(state: _BuildState, votes: list[Vote]) -> None:
    """Sum vote confidences over surface match; apply to Propose-derived records only."""
    for record in state.records:
        if record.kind != "propose":
            continue
        boost = sum(v.confidence for v in votes if v.option.surface == record.surface)
        record.base_score = max(0.0, min(1.0, record.base_score + boost))
