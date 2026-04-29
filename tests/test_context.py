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
