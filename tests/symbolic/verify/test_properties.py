"""Tests for council/symbolic/verify/properties.py — 10 named properties + registry.

Each property gets a positive trace (TOP or UNKNOWN) and a negative trace
(BOTTOM verdict). Traces are crafted using the to_events() schema directly
to keep tests self-contained.
"""

import pytest

from council.symbolic.verify.monitor import LTL3Monitor, Property, Verdict
from council.symbolic.verify.properties import (
    PROPERTY_REGISTRY,
    BoundedRound,
    ChallengeBeforeConsensus,
    EventuallyDecide,
    FairnessOfRoles,
    ModalitySafe,
    NoMonotoneAgreementCollapse,
    NoPrematureConsensus,
    NoSycophancyCascade,
    ProvenanceCompleteness,
    RefutationReachable,
)


def _step_trace(monitor: LTL3Monitor, events: list[dict[str, object]]) -> Verdict:
    """Step the monitor through events and return the final verdict."""
    final = monitor.current_verdict
    for e in events:
        final = monitor.step(e)
    return final


def _fill(**flags: bool) -> dict[str, object]:
    """Build an event dict with every AP defaulting to False except those overridden."""
    base: dict[str, object] = {
        "is_propose": False,
        "is_challenge": False,
        "is_concede": False,
        "is_retract": False,
        "is_question": False,
        "is_clarify": False,
        "is_vote": False,
        "is_abstain": False,
        "is_pass": False,
        "has_evidence": False,
        "has_prior_challenge": False,
        "same_agent_concede_run_ge_3": False,
    }
    base.update(flags)
    return base


# ---------------------------------------------------------------------------
# Registry contract
# ---------------------------------------------------------------------------

def test_property_registry_contains_ten_properties() -> None:
    assert len(PROPERTY_REGISTRY) == 10


def test_property_registry_keys_match_property_names() -> None:
    for name, cls in PROPERTY_REGISTRY.items():
        assert cls.name == name


@pytest.mark.parametrize("cls", list(PROPERTY_REGISTRY.values()))
def test_every_property_compiles_to_a_monitor(cls: type[Property]) -> None:
    """Every Property in the registry has a working compile() method."""
    p = cls()
    monitor = p.compile()
    assert isinstance(monitor, LTL3Monitor)


# ---------------------------------------------------------------------------
# 1. EventuallyDecide — F is_vote
# ---------------------------------------------------------------------------

def test_eventually_decide_positive() -> None:
    """A trace ending with a Vote: TOP."""
    m = EventuallyDecide().compile()
    assert _step_trace(m, [_fill(is_propose=True), _fill(is_challenge=True), _fill(is_vote=True)]) is Verdict.TOP


def test_eventually_decide_negative_stays_unknown_on_finite_trace() -> None:
    """No vote in a finite trace: UNKNOWN (live property; only BOTTOM at end-of-trace)."""
    m = EventuallyDecide().compile()
    final = _step_trace(m, [_fill(is_propose=True), _fill(is_challenge=True)])
    assert final is Verdict.UNKNOWN


# ---------------------------------------------------------------------------
# 2. NoSycophancyCascade — G !same_agent_concede_run_ge_3
# ---------------------------------------------------------------------------

def test_no_sycophancy_cascade_positive() -> None:
    """Traces with at most 2 same-agent concedes in a row stay UNKNOWN."""
    m = NoSycophancyCascade().compile()
    final = _step_trace(m, [
        _fill(is_concede=True, same_agent_concede_run_ge_3=False),
        _fill(is_concede=True, same_agent_concede_run_ge_3=False),
        _fill(is_propose=True),  # break the run
    ])
    assert final is Verdict.UNKNOWN


def test_no_sycophancy_cascade_negative() -> None:
    """3+ same-agent concedes triggers BOTTOM."""
    m = NoSycophancyCascade().compile()
    final = _step_trace(m, [
        _fill(is_concede=True, same_agent_concede_run_ge_3=False),
        _fill(is_concede=True, same_agent_concede_run_ge_3=False),
        _fill(is_concede=True, same_agent_concede_run_ge_3=True),
    ])
    assert final is Verdict.BOTTOM


# ---------------------------------------------------------------------------
# 3. NoPrematureConsensus — G (is_vote -> has_prior_challenge)
# ---------------------------------------------------------------------------

def test_no_premature_consensus_positive() -> None:
    """Vote happens after a challenge: UNKNOWN (G never returns TOP at runtime)."""
    m = NoPrematureConsensus().compile()
    final = _step_trace(m, [
        _fill(is_propose=True),
        _fill(is_challenge=True),
        _fill(is_vote=True, has_prior_challenge=True),
    ])
    assert final is Verdict.UNKNOWN


def test_no_premature_consensus_negative() -> None:
    """Vote without prior challenge: BOTTOM."""
    m = NoPrematureConsensus().compile()
    final = _step_trace(m, [
        _fill(is_propose=True),
        _fill(is_vote=True, has_prior_challenge=False),  # premature
    ])
    assert final is Verdict.BOTTOM


# ---------------------------------------------------------------------------
# 4. ProvenanceCompleteness — G (is_vote -> has_evidence)
# ---------------------------------------------------------------------------

def test_provenance_completeness_positive() -> None:
    m = ProvenanceCompleteness().compile()
    final = _step_trace(m, [
        _fill(is_propose=True, has_evidence=True),
        _fill(is_vote=True, has_evidence=True),
    ])
    assert final is Verdict.UNKNOWN


def test_provenance_completeness_negative() -> None:
    """Vote without evidence: BOTTOM."""
    m = ProvenanceCompleteness().compile()
    final = _step_trace(m, [
        _fill(is_vote=True, has_evidence=False),
    ])
    assert final is Verdict.BOTTOM


# ---------------------------------------------------------------------------
# 5. NoMonotoneAgreementCollapse — G (is_propose -> F (is_challenge || is_vote))
# ---------------------------------------------------------------------------

def test_no_monotone_agreement_collapse_positive() -> None:
    m = NoMonotoneAgreementCollapse().compile()
    final = _step_trace(m, [
        _fill(is_propose=True),
        _fill(is_challenge=True),  # propose discharged by challenge
        _fill(is_vote=True),
    ])
    assert final is Verdict.UNKNOWN


def test_no_monotone_agreement_collapse_no_propose_stays_unknown() -> None:
    """No proposes → vacuously UNKNOWN (G(true) is always UNKNOWN at runtime)."""
    m = NoMonotoneAgreementCollapse().compile()
    final = _step_trace(m, [_fill(is_question=True), _fill(is_clarify=True)])
    assert final is Verdict.UNKNOWN


# ---------------------------------------------------------------------------
# 6. ChallengeBeforeConsensus — F (is_challenge && F is_vote)
# ---------------------------------------------------------------------------

def test_challenge_before_consensus_positive() -> None:
    """Challenge followed eventually by a vote: TOP."""
    m = ChallengeBeforeConsensus().compile()
    final = _step_trace(m, [
        _fill(is_propose=True),
        _fill(is_challenge=True),
        _fill(is_vote=True),
    ])
    assert final is Verdict.TOP


def test_challenge_before_consensus_only_vote_no_challenge() -> None:
    """Vote without any challenge: stays UNKNOWN (challenge could come later)."""
    m = ChallengeBeforeConsensus().compile()
    final = _step_trace(m, [_fill(is_vote=True)])
    assert final is Verdict.UNKNOWN


# ---------------------------------------------------------------------------
# 7. RefutationReachable — F (is_challenge && F is_vote)
# ---------------------------------------------------------------------------

def test_refutation_reachable_positive() -> None:
    m = RefutationReachable().compile()
    final = _step_trace(m, [
        _fill(is_propose=True),
        _fill(is_challenge=True),
        _fill(is_vote=True),
    ])
    assert final is Verdict.TOP


def test_refutation_reachable_no_challenge_stays_unknown() -> None:
    m = RefutationReachable().compile()
    final = _step_trace(m, [_fill(is_propose=True), _fill(is_vote=True)])
    assert final is Verdict.UNKNOWN


# ---------------------------------------------------------------------------
# 8. FairnessOfRoles — F is_propose && F is_challenge
# ---------------------------------------------------------------------------

def test_fairness_of_roles_positive() -> None:
    m = FairnessOfRoles().compile()
    final = _step_trace(m, [_fill(is_propose=True), _fill(is_challenge=True)])
    assert final is Verdict.TOP


def test_fairness_of_roles_only_propose_stays_unknown() -> None:
    """Only proposes, no challenges: UNKNOWN (challenge could happen later)."""
    m = FairnessOfRoles().compile()
    final = _step_trace(m, [_fill(is_propose=True), _fill(is_propose=True)])
    assert final is Verdict.UNKNOWN


# ---------------------------------------------------------------------------
# 9. ModalitySafe — G (is_propose -> (has_evidence || F is_challenge))
# ---------------------------------------------------------------------------

def test_modality_safe_positive_with_evidence() -> None:
    """Propose with evidence: vacuously satisfies the disjunction."""
    m = ModalitySafe().compile()
    final = _step_trace(m, [_fill(is_propose=True, has_evidence=True)])
    assert final is Verdict.UNKNOWN


def test_modality_safe_positive_with_later_challenge() -> None:
    """Unevidenced propose followed by challenge: discharges the F obligation."""
    m = ModalitySafe().compile()
    final = _step_trace(m, [
        _fill(is_propose=True, has_evidence=False),
        _fill(is_challenge=True),
    ])
    assert final is Verdict.UNKNOWN


def test_modality_safe_unevidenced_propose_stays_unknown() -> None:
    """Unevidenced propose with no challenge yet: stays UNKNOWN."""
    m = ModalitySafe().compile()
    final = _step_trace(m, [_fill(is_propose=True, has_evidence=False)])
    assert final is Verdict.UNKNOWN


# ---------------------------------------------------------------------------
# 10. BoundedRound — F is_vote (k tracked at instance level)
# ---------------------------------------------------------------------------

def test_bounded_round_default_k() -> None:
    p = BoundedRound()
    assert p.k == 10


def test_bounded_round_custom_k() -> None:
    p = BoundedRound(k=3)
    assert p.k == 3


def test_bounded_round_rejects_zero_k() -> None:
    with pytest.raises(ValueError, match="must be >= 1"):
        BoundedRound(k=0)


def test_bounded_round_rejects_negative_k() -> None:
    with pytest.raises(ValueError, match="must be >= 1"):
        BoundedRound(k=-1)


def test_bounded_round_compile_returns_eventually_monitor() -> None:
    """BoundedRound's L1 monitor is F(is_vote); the k bound is W8's job."""
    m = BoundedRound(k=2).compile()
    assert _step_trace(m, [_fill(is_vote=True)]) is Verdict.TOP
