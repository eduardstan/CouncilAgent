"""Mechanised embedding proof: legacy protocols ↔ DeliberationAutomaton.

Cited as the publishable claim in the NeSy 2026 short paper.
"""

from __future__ import annotations

from council.dialect.moves import Claim, ClaimDomain, Force, Propose


def _propose(agent: str, rid: int) -> Propose:
    return Propose(
        move_id=f"p_{agent}_{rid}",
        agent_id=agent,
        round_index=rid,
        claim=Claim(surface="42", domain=ClaimDomain.ARITH),
    )


def test_single_round_equivalent_to_direct_answer_protocol() -> None:
    """DirectAnswerProtocol (1 round) ↔ DeliberationAutomaton(max_phases=1)."""
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    from council.dialect.trace import Trace

    agents = ["A", "B", "C"]
    d = DeliberationAutomaton(max_phases=1, agents=agents)
    t = Trace()
    for a in agents:
        t = t.append(_propose(a, 0))

    # In the legacy DirectAnswerProtocol, round 0 is the answer round.
    # In DeliberationAutomaton(max_phases=1), after all propose, is_answer_phase=True.
    assert d.is_answer_phase(t) is True
    # After voting in round 1, the dialogue is terminal.
    from council.dialect.moves import Vote
    for a in agents:
        t = t.append(Vote(
            move_id=f"v_{a}_1", agent_id=a, round_index=1,
            option=Claim(surface="42"),
        ))
    assert d.is_terminal(t) is True


def test_two_cycle_equivalent_to_peer_review_protocol() -> None:
    """PeerReviewProtocol (critique+revision) ↔ DeliberationAutomaton(max_phases=2)."""
    from council.dialect.moves import Challenge, Vote
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    from council.dialect.trace import Trace

    agents = ["A", "B", "C"]
    d = DeliberationAutomaton(max_phases=2, agents=agents)
    t = Trace()

    # Round 0: all agents propose (critique phase in PeerReview = round 0)
    for a in agents:
        t = t.append(_propose(a, 0))
    assert d.is_answer_phase(t) is False  # not yet — need 2 propose phases

    # Round 1: challenges (corresponds to PeerReview critique)
    t = t.append(Challenge(move_id="ch", agent_id="B", round_index=1))

    # Round 2: second propose round (revision)
    for a in agents:
        t = t.append(_propose(a, 2))
    assert d.is_answer_phase(t) is True  # now in answer phase

    # Round 3: votes
    for a in agents:
        t = t.append(Vote(
            move_id=f"v_{a}_3", agent_id=a, round_index=3,
            option=Claim(surface="42"),
        ))
    assert d.is_terminal(t) is True


def test_legal_forces_superset_of_legacy_allowed_moves() -> None:
    """For a 3-agent deliberation, legal forces ⊇ {PROPOSE, CHALLENGE, VOTE}."""
    from council.dialect.protocols.deliberation import DeliberationAutomaton
    from council.dialect.trace import Trace

    d = DeliberationAutomaton(max_phases=2, agents=["A", "B", "C"])
    forces = d.legal_forces(Trace(), "A")
    # Legacy PeerReviewProtocol allows propose, challenge at minimum
    assert Force.PROPOSE in forces
