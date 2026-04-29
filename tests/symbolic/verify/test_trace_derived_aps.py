"""Tests for the W1 derived boolean APs in Trace.to_events().

Covers has_evidence, has_prior_challenge, same_agent_concede_run_ge_3.
"""

from council.dialect.moves import Challenge, Claim, Concede, Force, Propose, Vote
from council.dialect.trace import Trace


def _prop(agent: str = "A", rnd: int = 0, evidence: tuple[str, ...] = ()) -> Propose:
    return Propose(
        move_id=f"p-{agent}-{rnd}",
        agent_id=agent,
        round_index=rnd,
        claim=Claim(surface="ans", evidence=evidence),
    )


def _chal(agent: str = "A", rnd: int = 0) -> Challenge:
    return Challenge(move_id=f"c-{agent}-{rnd}", agent_id=agent, round_index=rnd)


def _conc(agent: str = "A", rnd: int = 0) -> Concede:
    return Concede(move_id=f"cc-{agent}-{rnd}", agent_id=agent, round_index=rnd)


def _vote(agent: str = "A", rnd: int = 0, evidence: tuple[str, ...] = ()) -> Vote:
    return Vote(
        move_id=f"v-{agent}-{rnd}",
        agent_id=agent,
        round_index=rnd,
        option=Claim(surface="yes", evidence=evidence),
    )


def _make_trace(*moves: object) -> Trace:
    t = Trace()
    for m in moves:
        t = t.append(m)  # type: ignore[arg-type]
    return t


# ---------------------------------------------------------------------------
# has_evidence
# ---------------------------------------------------------------------------

def test_has_evidence_propose_true() -> None:
    trace = _make_trace(_prop(evidence=("e1",)))
    events = trace.to_events()
    assert events[0]["has_evidence"] is True


def test_has_evidence_propose_false() -> None:
    trace = _make_trace(_prop(evidence=()))
    events = trace.to_events()
    assert events[0]["has_evidence"] is False


def test_has_evidence_vote_true() -> None:
    trace = _make_trace(_vote(evidence=("ref1",)))
    events = trace.to_events()
    assert events[0]["has_evidence"] is True


def test_has_evidence_vote_false() -> None:
    trace = _make_trace(_vote(evidence=()))
    events = trace.to_events()
    assert events[0]["has_evidence"] is False


def test_has_evidence_non_propose_false() -> None:
    """Challenge moves are never evidence-bearing."""
    trace = _make_trace(_chal())
    events = trace.to_events()
    assert events[0]["has_evidence"] is False


def test_has_evidence_concede_false() -> None:
    trace = _make_trace(_conc())
    events = trace.to_events()
    assert events[0]["has_evidence"] is False


# ---------------------------------------------------------------------------
# has_prior_challenge
# ---------------------------------------------------------------------------

def test_has_prior_challenge_false_no_challenge() -> None:
    """Traces with no Challenge at all: all events are False."""
    trace = _make_trace(_prop("A", 0), _prop("B", 0), _prop("A", 1))
    for event in trace.to_events():
        assert event["has_prior_challenge"] is False


def test_has_prior_challenge_false_on_the_challenge_itself() -> None:
    """The Challenge event does NOT report a prior challenge on itself."""
    trace = _make_trace(_chal("A", 0))
    assert trace.to_events()[0]["has_prior_challenge"] is False


def test_has_prior_challenge_true_after_challenge() -> None:
    """Events after a Challenge see has_prior_challenge=True."""
    trace = _make_trace(_prop("A", 0), _chal("B", 0), _prop("A", 1))
    events = trace.to_events()
    assert events[0]["has_prior_challenge"] is False  # before the challenge
    assert events[1]["has_prior_challenge"] is False  # the challenge itself
    assert events[2]["has_prior_challenge"] is True   # after the challenge


def test_has_prior_challenge_stays_true_after_first_challenge() -> None:
    """Once a Challenge is seen, all subsequent events are True regardless of type."""
    trace = _make_trace(_prop("A", 0), _chal("B", 0), _conc("A", 1), _prop("A", 2))
    events = trace.to_events()
    assert events[2]["has_prior_challenge"] is True
    assert events[3]["has_prior_challenge"] is True


# ---------------------------------------------------------------------------
# same_agent_concede_run_ge_3
# ---------------------------------------------------------------------------

def test_same_agent_concede_run_ge_3_false_single() -> None:
    trace = _make_trace(_conc("A", 0))
    assert trace.to_events()[0]["same_agent_concede_run_ge_3"] is False


def test_same_agent_concede_run_ge_3_false_run_of_2() -> None:
    """Two consecutive Concedes from the same agent: both False."""
    trace = _make_trace(_conc("A", 0), _conc("A", 1))
    events = trace.to_events()
    assert events[0]["same_agent_concede_run_ge_3"] is False
    assert events[1]["same_agent_concede_run_ge_3"] is False


def test_same_agent_concede_run_ge_3_true_on_third() -> None:
    """Three consecutive Concedes from same agent: first two False, third True."""
    trace = _make_trace(_conc("A", 0), _conc("A", 1), _conc("A", 2))
    events = trace.to_events()
    assert events[0]["same_agent_concede_run_ge_3"] is False
    assert events[1]["same_agent_concede_run_ge_3"] is False
    assert events[2]["same_agent_concede_run_ge_3"] is True


def test_same_agent_concede_run_ge_3_stays_true_on_fourth() -> None:
    trace = _make_trace(_conc("A", 0), _conc("A", 1), _conc("A", 2), _conc("A", 3))
    events = trace.to_events()
    assert events[3]["same_agent_concede_run_ge_3"] is True


def test_same_agent_concede_run_reset_by_propose() -> None:
    """Concede–Propose–Concede–Concede: run resets; last event has run=2, flag=False."""
    trace = _make_trace(_conc("A", 0), _prop("A", 1), _conc("A", 2), _conc("A", 3))
    events = trace.to_events()
    assert events[0]["same_agent_concede_run_ge_3"] is False  # run=1
    assert events[1]["same_agent_concede_run_ge_3"] is False  # non-Concede, run reset
    assert events[2]["same_agent_concede_run_ge_3"] is False  # run=1 (restarted)
    assert events[3]["same_agent_concede_run_ge_3"] is False  # run=2


def test_different_agents_runs_are_independent() -> None:
    """Concede(A), Concede(B), Concede(A) — A's run is 2, not 3."""
    trace = _make_trace(_conc("A", 0), _conc("B", 0), _conc("A", 1))
    events = trace.to_events()
    assert events[0]["same_agent_concede_run_ge_3"] is False  # A run=1
    assert events[1]["same_agent_concede_run_ge_3"] is False  # B run=1
    assert events[2]["same_agent_concede_run_ge_3"] is False  # A run=2 (B did not count)


def test_non_concede_does_not_trigger_flag() -> None:
    """A Challenge move always has same_agent_concede_run_ge_3=False."""
    trace = _make_trace(_chal("A", 0), _chal("A", 1), _chal("A", 2))
    for event in trace.to_events():
        assert event["same_agent_concede_run_ge_3"] is False
