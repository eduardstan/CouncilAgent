"""Tests for council/context.py — Confidence tagged union, ProvenanceReceipt, etc."""

from __future__ import annotations

import dataclasses

import pytest

from council.dialect.moves import Claim, Propose
from council.dialect.trace import Trace

# ---------------------------------------------------------------------------
# Confidence tagged union — Constitution §5
# ---------------------------------------------------------------------------

def test_confidence_tags_are_distinct() -> None:
    from council.context import (
        BAFMarginConfidence,
        CopelandConfidence,
        JSDConfidence,
        MonitorVerdictConfidence,
    )

    j = JSDConfidence(value=0.8)
    b = BAFMarginConfidence(value=0.7)
    m = MonitorVerdictConfidence(value=0.9)
    c = CopelandConfidence(value=0.6)
    assert j.tag == "jsd"
    assert b.tag == "baf"
    assert m.tag == "monitor"
    assert c.tag == "copeland"


def test_confidence_values_are_frozen() -> None:
    from council.context import JSDConfidence

    conf = JSDConfidence(value=0.5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        conf.value = 0.9  # type: ignore[misc]


def test_confidence_is_tagged_type_union() -> None:

    from council.context import (
        BAFMarginConfidence,
        CopelandConfidence,
        JSDConfidence,
        MonitorVerdictConfidence,
    )

    # Each subtype is in the Confidence union
    for cls in (JSDConfidence, BAFMarginConfidence, MonitorVerdictConfidence, CopelandConfidence):
        instance = cls(value=0.5)
        assert isinstance(instance, cls)


# ---------------------------------------------------------------------------
# ProvenanceReceipt
# ---------------------------------------------------------------------------

def test_provenance_receipt_empty_trace_is_complete() -> None:
    from council.context import ProvenanceReceipt

    receipt = ProvenanceReceipt(trace=Trace())
    assert receipt.is_complete() is True


def test_provenance_receipt_with_move_and_cost_is_complete() -> None:
    from council.context import ProvenanceReceipt

    move = Propose(
        move_id="m1",
        agent_id="a1",
        round_index=0,
        claim=Claim(surface="42"),
        confidence=0.9,
    )
    trace = Trace().append(move)
    receipt = ProvenanceReceipt(
        trace=trace,
        cost_ledger=(("m1", 0.001),),
    )
    assert receipt.is_complete() is True


def test_provenance_receipt_missing_cost_is_incomplete() -> None:
    from council.context import ProvenanceReceipt

    move = Propose(
        move_id="m1",
        agent_id="a1",
        round_index=0,
        claim=Claim(surface="42"),
    )
    trace = Trace().append(move)
    receipt = ProvenanceReceipt(trace=trace)  # no cost_ledger
    assert receipt.is_complete() is False


# ---------------------------------------------------------------------------
# §11 clauses — Vote-evidence, intervention zero-cost, bottom-verdict-intervention
# ---------------------------------------------------------------------------

def test_intervention_moves_with_zero_cost_satisfy_is_complete() -> None:
    """Intervention moves must appear in cost_ledger with cost=0.0 (W1 PR8 fix).

    Until the constitution-audit fix, intervention moves were silently absent
    from cost_ledger and is_complete() returned False even on clean runs.
    """
    from council.context import ProvenanceReceipt
    from council.dialect.moves import Challenge
    from council.symbolic.verify.interventions import INTERVENTION_AGENT_ID

    propose = Propose(
        move_id="p0", agent_id="A", round_index=0,
        claim=Claim(surface="ans", evidence=("e1",)),
    )
    intervention_move = Challenge(
        move_id="i0", agent_id=INTERVENTION_AGENT_ID, round_index=0,
    )
    trace = Trace().append(propose).append(intervention_move)
    receipt = ProvenanceReceipt(
        trace=trace,
        cost_ledger=(("p0", 0.001), ("i0", 0.0)),
    )
    assert receipt.is_complete() is True


def test_intervention_moves_without_cost_entry_fail_is_complete() -> None:
    """Even moves from INTERVENTION_AGENT_ID need an explicit zero-cost ledger
    entry so that the receipt can audit their provenance.
    """
    from council.context import ProvenanceReceipt
    from council.dialect.moves import Challenge
    from council.symbolic.verify.interventions import INTERVENTION_AGENT_ID

    propose = Propose(
        move_id="p0", agent_id="A", round_index=0,
        claim=Claim(surface="ans", evidence=("e1",)),
    )
    intervention_move = Challenge(
        move_id="i0", agent_id=INTERVENTION_AGENT_ID, round_index=0,
    )
    trace = Trace().append(propose).append(intervention_move)
    receipt = ProvenanceReceipt(
        trace=trace,
        cost_ledger=(("p0", 0.001),),  # i0 missing
    )
    assert receipt.is_complete() is False


def test_vote_with_evidence_passes_is_complete() -> None:
    """§11 Vote-evidence clause: Vote with non-empty evidence is OK."""
    from council.context import ProvenanceReceipt
    from council.dialect.moves import Vote

    vote = Vote(
        move_id="v0", agent_id="A", round_index=0,
        option=Claim(surface="X", evidence=("e1",)),
    )
    receipt = ProvenanceReceipt(
        trace=Trace().append(vote),
        cost_ledger=(("v0", 0.002),),
    )
    assert receipt.is_complete() is True


def test_vote_without_evidence_fails_is_complete() -> None:
    """§11 Vote-evidence clause: Vote without evidence makes is_complete() False."""
    from council.context import ProvenanceReceipt
    from council.dialect.moves import Vote

    vote = Vote(
        move_id="v0", agent_id="A", round_index=0,
        option=Claim(surface="X", evidence=()),  # empty
    )
    receipt = ProvenanceReceipt(
        trace=Trace().append(vote),
        cost_ledger=(("v0", 0.002),),
    )
    assert receipt.is_complete() is False


def test_propose_without_evidence_does_not_fail_is_complete() -> None:
    """§11 Vote-evidence clause is specifically about Vote, not Propose.

    A Propose without evidence is fine — it can be hypothetical / exploratory.
    Only Votes are committed decisions and must justify themselves.
    """
    from council.context import ProvenanceReceipt

    propose = Propose(
        move_id="p0", agent_id="A", round_index=0,
        claim=Claim(surface="ans", evidence=()),  # empty
    )
    receipt = ProvenanceReceipt(
        trace=Trace().append(propose),
        cost_ledger=(("p0", 0.001),),
    )
    assert receipt.is_complete() is True


def test_bottom_verdict_with_intervention_move_passes() -> None:
    """§11 bottom-verdict clause: every BOTTOM verdict must have a covering
    intervention move (a move from INTERVENTION_AGENT_ID at >= the verdict's
    round_index).
    """
    from council.context import ProvenanceReceipt
    from council.dialect.moves import Challenge
    from council.symbolic.verify.interventions import INTERVENTION_AGENT_ID
    from council.termination import MonitorVerdict

    propose = Propose(
        move_id="p0", agent_id="A", round_index=0,
        claim=Claim(surface="ans", evidence=("e1",)),
    )
    intervention_move = Challenge(
        move_id="i0", agent_id=INTERVENTION_AGENT_ID, round_index=0,
    )
    trace = Trace().append(propose).append(intervention_move)
    receipt = ProvenanceReceipt(
        trace=trace,
        cost_ledger=(("p0", 0.001), ("i0", 0.0)),
        monitor_verdicts=(MonitorVerdict("EventuallyDecide", "bottom", 0),),
    )
    assert receipt.is_complete() is True


def test_bottom_verdict_without_intervention_move_fails() -> None:
    """A BOTTOM verdict with no covering intervention move is incomplete."""
    from council.context import ProvenanceReceipt
    from council.termination import MonitorVerdict

    propose = Propose(
        move_id="p0", agent_id="A", round_index=0,
        claim=Claim(surface="ans", evidence=("e1",)),
    )
    receipt = ProvenanceReceipt(
        trace=Trace().append(propose),
        cost_ledger=(("p0", 0.001),),
        monitor_verdicts=(MonitorVerdict("EventuallyDecide", "bottom", 0),),
    )
    assert receipt.is_complete() is False


def test_top_and_unknown_verdicts_do_not_require_intervention() -> None:
    """§11 clause is gated on BOTTOM verdicts only; TOP / UNKNOWN are fine alone."""
    from council.context import ProvenanceReceipt
    from council.termination import MonitorVerdict

    propose = Propose(
        move_id="p0", agent_id="A", round_index=0,
        claim=Claim(surface="ans", evidence=("e1",)),
    )
    receipt = ProvenanceReceipt(
        trace=Trace().append(propose),
        cost_ledger=(("p0", 0.001),),
        monitor_verdicts=(
            MonitorVerdict("EventuallyDecide", "top", 0),
            MonitorVerdict("NoSycophancyCascade", "unknown", 0),
        ),
    )
    assert receipt.is_complete() is True


def test_multiple_bottom_verdicts_each_need_an_intervention() -> None:
    """Two BOTTOM verdicts in different rounds require an intervention move per
    round (or a single intervention covering the later one if applied at the
    earliest round of trouble — but here we only have one intervention at
    round 0, and the second BOTTOM is at round 1, so it should fail)."""
    from council.context import ProvenanceReceipt
    from council.dialect.moves import Challenge
    from council.symbolic.verify.interventions import INTERVENTION_AGENT_ID
    from council.termination import MonitorVerdict

    propose0 = Propose(
        move_id="p0", agent_id="A", round_index=0,
        claim=Claim(surface="ans", evidence=("e1",)),
    )
    intervention0 = Challenge(
        move_id="i0", agent_id=INTERVENTION_AGENT_ID, round_index=0,
    )
    propose1 = Propose(
        move_id="p1", agent_id="A", round_index=1,
        claim=Claim(surface="ans2", evidence=("e2",)),
    )
    trace = Trace().append(propose0).append(intervention0).append(propose1)
    receipt = ProvenanceReceipt(
        trace=trace,
        cost_ledger=(("p0", 0.001), ("i0", 0.0), ("p1", 0.001)),
        monitor_verdicts=(
            MonitorVerdict("EventuallyDecide", "bottom", 0),  # covered by i0
            MonitorVerdict("NoPrematureConsensus", "bottom", 1),  # NOT covered
        ),
    )
    assert receipt.is_complete() is False


# ---------------------------------------------------------------------------
# CouncilResponse — confidence must be tagged (Constitution §5)
# ---------------------------------------------------------------------------

def test_council_response_holds_tagged_confidence() -> None:
    from council.context import CopelandConfidence, CouncilResponse, ProvenanceReceipt

    conf = CopelandConfidence(value=0.5)
    receipt = ProvenanceReceipt(trace=Trace())
    resp = CouncilResponse(answer="42", confidence=conf, receipt=receipt)
    assert resp.confidence is conf
    assert resp.confidence.value == 0.5
    assert resp.confidence.tag == "copeland"


def test_council_response_is_frozen() -> None:
    from council.context import CopelandConfidence, CouncilResponse, ProvenanceReceipt

    resp = CouncilResponse(
        answer="42",
        confidence=CopelandConfidence(value=0.5),
        receipt=ProvenanceReceipt(trace=Trace()),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        resp.answer = "43"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# VisibilityContext — anonymisation carrier (Constitution §10)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# CouncilContext — tool_client field (W1 Patch B)
# ---------------------------------------------------------------------------

def test_council_context_default_tool_client_is_none() -> None:
    """CouncilContext.tool_client defaults to None — no callsite changes required."""
    from council.context import CouncilContext
    from council.models import FakeModelClient
    from council.termination import FixedRounds
    from council.topology import CompleteGraphTopology

    ctx = CouncilContext(
        agents=("a", "b"),
        model_client=FakeModelClient(),
        protocol=object(),
        topology=CompleteGraphTopology(2),
        termination=FixedRounds(1),
    )
    assert ctx.tool_client is None


def test_council_context_accepts_tool_client() -> None:
    """CouncilContext accepts an explicit ToolClient instance (StubToolClient here)."""
    from council.context import CouncilContext
    from council.models import FakeModelClient
    from council.termination import FixedRounds
    from council.tools import StubToolClient
    from council.topology import CompleteGraphTopology

    stub = StubToolClient()
    ctx = CouncilContext(
        agents=("a", "b"),
        model_client=FakeModelClient(),
        protocol=object(),
        topology=CompleteGraphTopology(2),
        termination=FixedRounds(1),
        tool_client=stub,
    )
    assert ctx.tool_client is stub


# ---------------------------------------------------------------------------

def test_visibility_context_carries_anonymize_flag() -> None:
    from council.context import VisibilityContext

    vc = VisibilityContext(
        visible_moves=(),
        agent_id="a1",
        anonymize=True,
        round_index=0,
    )
    assert vc.anonymize is True
    assert vc.agent_id == "a1"


# ---------------------------------------------------------------------------
# Patch D — ProvenanceReceipt.qbaf is typed as QBAF | None
# ---------------------------------------------------------------------------


def test_provenance_receipt_qbaf_field_default_none() -> None:
    """Patch D: qbaf field defaults to None for non-L2 callers (W0/W1)."""
    from council.context import ProvenanceReceipt
    receipt = ProvenanceReceipt(trace=Trace())
    assert receipt.qbaf is None


def test_provenance_receipt_accepts_qbaf_instance() -> None:
    """Patch D: qbaf field accepts a real QBAF instance."""
    from council.context import ProvenanceReceipt
    from council.symbolic.argue.baf import QBAF, Argument

    arg = Argument(arg_id="p1", claim_surface="X", base_score=0.5)
    qbaf = QBAF(arguments=(arg,), attacks=(), supports=())
    receipt = ProvenanceReceipt(trace=Trace(), qbaf=qbaf)
    assert receipt.qbaf is qbaf


# ---------------------------------------------------------------------------
# Patch E — is_complete() QBAF clause (Constitution §11)
# ---------------------------------------------------------------------------


def test_is_complete_qbaf_none_passes() -> None:
    """Patch E: when qbaf is None, the QBAF clause is vacuously satisfied."""
    from council.context import ProvenanceReceipt

    p1 = Propose(
        move_id="p1",
        agent_id="A",
        round_index=0,
        claim=Claim(surface="X"),
        confidence=0.5,
    )
    trace = Trace().append(p1)
    receipt = ProvenanceReceipt(
        trace=trace,
        qbaf=None,
        cost_ledger=(("p1", 0.0),),
    )
    assert receipt.is_complete() is True


def test_is_complete_qbaf_matches_propose_count_passes() -> None:
    """Patch E: when qbaf has an Argument per Propose move_id, the
    Constitution §11 QBAF clause is satisfied."""
    from council.context import ProvenanceReceipt
    from council.symbolic.argue.baf import QBAF, Argument

    p1 = Propose(
        move_id="p1",
        agent_id="A",
        round_index=0,
        claim=Claim(surface="X"),
        confidence=0.5,
    )
    p2 = Propose(
        move_id="p2",
        agent_id="B",
        round_index=0,
        claim=Claim(surface="Y"),
        confidence=0.4,
    )
    trace = Trace().append(p1).append(p2)
    qbaf = QBAF(
        arguments=(
            Argument(arg_id="p1", claim_surface="X", base_score=0.5),
            Argument(arg_id="p2", claim_surface="Y", base_score=0.4),
        ),
        attacks=(),
        supports=(),
    )
    receipt = ProvenanceReceipt(
        trace=trace,
        qbaf=qbaf,
        cost_ledger=(("p1", 0.0), ("p2", 0.0)),
    )
    assert receipt.is_complete() is True


def test_is_complete_qbaf_missing_propose_argument_fails() -> None:
    """Patch E: a Propose without a corresponding Argument fails the clause."""
    from council.context import ProvenanceReceipt
    from council.symbolic.argue.baf import QBAF, Argument

    p1 = Propose(
        move_id="p1",
        agent_id="A",
        round_index=0,
        claim=Claim(surface="X"),
        confidence=0.5,
    )
    p2 = Propose(
        move_id="p2",
        agent_id="B",
        round_index=0,
        claim=Claim(surface="Y"),
        confidence=0.4,
    )
    trace = Trace().append(p1).append(p2)
    # qbaf is missing arg for p2
    qbaf = QBAF(
        arguments=(
            Argument(arg_id="p1", claim_surface="X", base_score=0.5),
        ),
        attacks=(),
        supports=(),
    )
    receipt = ProvenanceReceipt(
        trace=trace,
        qbaf=qbaf,
        cost_ledger=(("p1", 0.0), ("p2", 0.0)),
    )
    assert receipt.is_complete() is False


def test_is_complete_qbaf_with_extra_arguments_passes() -> None:
    """Patch E: extra Arguments (Challenge/Concede-derived) are allowed —
    the bijection is one-way (every Propose has an Argument), not strict
    equality. ADR-0009 documents the operational reformulation of §11."""
    from council.context import ProvenanceReceipt
    from council.symbolic.argue.baf import QBAF, Argument

    p1 = Propose(
        move_id="p1",
        agent_id="A",
        round_index=0,
        claim=Claim(surface="X"),
        confidence=0.5,
    )
    trace = Trace().append(p1)
    # qbaf has an extra "c1" argument (Challenge-derived)
    qbaf = QBAF(
        arguments=(
            Argument(arg_id="p1", claim_surface="X", base_score=0.5),
            Argument(arg_id="c1", claim_surface="bad reasoning", base_score=0.7),
        ),
        attacks=(),
        supports=(),
    )
    receipt = ProvenanceReceipt(
        trace=trace,
        qbaf=qbaf,
        cost_ledger=(("p1", 0.0),),
    )
    # Every Propose has a matching Argument → clause passes
    assert receipt.is_complete() is True
