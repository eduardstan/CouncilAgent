"""Tests for council/symbolic/argue/coupled_atl.py — ATL fragment helper.

The ATL fragment computes the set of arg_ids that have at least one agent
witness with non-empty evidence (the minimal one-coalition existential
`<<{i}>> X witness_evidence(arg)` from ADR-0012). It's a finite-trace
existential check, observable directly without an ATL model checker.
"""

from __future__ import annotations

from council.dialect.moves import Claim, ClaimDomain, Propose, Vote
from council.dialect.trace import Trace
from council.symbolic.argue.coupled_atl import evidence_backed_arg_ids


def _propose(
    move_id: str,
    *,
    surface: str = "X",
    agent_id: str = "A",
    confidence: float = 0.5,
    evidence: tuple[str, ...] = (),
) -> Propose:
    return Propose(
        move_id=move_id,
        agent_id=agent_id,
        round_index=0,
        claim=Claim(surface=surface, domain=ClaimDomain.FREE, evidence=evidence),
        confidence=confidence,
    )


def _vote(
    move_id: str,
    *,
    surface: str = "X",
    agent_id: str = "A",
    confidence: float = 0.5,
    evidence: tuple[str, ...] = (),
) -> Vote:
    return Vote(
        move_id=move_id,
        agent_id=agent_id,
        round_index=0,
        option=Claim(surface=surface, evidence=evidence),
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Empty / degenerate
# ---------------------------------------------------------------------------


class TestEmptyTrace:
    def test_empty_trace_returns_empty_set(self) -> None:
        assert evidence_backed_arg_ids(Trace()) == frozenset()

    def test_returns_frozenset(self) -> None:
        result = evidence_backed_arg_ids(Trace())
        assert isinstance(result, frozenset)


# ---------------------------------------------------------------------------
# Propose with evidence -> arg_id backed
# ---------------------------------------------------------------------------


class TestProposeEvidenceBacking:
    def test_propose_with_evidence_is_backed(self) -> None:
        trace = Trace().append(
            _propose("p1", evidence=("source-A",))
        )
        assert evidence_backed_arg_ids(trace) == frozenset({"p1"})

    def test_propose_without_evidence_not_backed(self) -> None:
        trace = Trace().append(_propose("p1", evidence=()))
        assert evidence_backed_arg_ids(trace) == frozenset()

    def test_multiple_proposes_some_backed(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", evidence=("witness-1",)))
            .append(_propose("p2", evidence=()))
            .append(_propose("p3", evidence=("witness-3a", "witness-3b")))
        )
        assert evidence_backed_arg_ids(trace) == frozenset({"p1", "p3"})


# ---------------------------------------------------------------------------
# Vote with evidence -> matching Propose arg_id backed
# ---------------------------------------------------------------------------


class TestVoteEvidenceBacking:
    def test_vote_with_evidence_backs_matching_propose(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X", evidence=()))
            .append(_vote("v1", surface="X", evidence=("vote-witness",)))
        )
        # The vote carries evidence and matches p1's claim.surface — p1 is backed.
        assert evidence_backed_arg_ids(trace) == frozenset({"p1"})

    def test_vote_without_evidence_does_not_back(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X", evidence=()))
            .append(_vote("v1", surface="X", evidence=()))
        )
        assert evidence_backed_arg_ids(trace) == frozenset()

    def test_vote_with_no_matching_propose_ignored(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X", evidence=()))
            .append(_vote("v1", surface="Y", evidence=("witness",)))
        )
        # Vote's option ("Y") doesn't match p1's claim ("X") — no backing
        assert evidence_backed_arg_ids(trace) == frozenset()


# ---------------------------------------------------------------------------
# T3 counterexample scenario
# ---------------------------------------------------------------------------


class TestT3Counterexample:
    """The 3-agent unanimous-vote-without-evidence trace from T3.

    Three agents all Propose/Vote for "X" with no evidence. No backing.
    """

    def test_three_agents_no_evidence_anywhere(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X", agent_id="A", evidence=()))
            .append(_propose("p2", surface="X", agent_id="B", evidence=()))
            .append(_propose("p3", surface="X", agent_id="C", evidence=()))
            .append(_vote("v1", surface="X", agent_id="A", evidence=()))
            .append(_vote("v2", surface="X", agent_id="B", evidence=()))
            .append(_vote("v3", surface="X", agent_id="C", evidence=()))
        )
        # No agent provides evidence -> no arg_id is backed
        assert evidence_backed_arg_ids(trace) == frozenset()

    def test_three_agents_one_provides_evidence_one_backed(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="X", agent_id="A", evidence=()))
            .append(_propose("p2", surface="X", agent_id="B", evidence=()))
            .append(_propose("p3", surface="X", agent_id="C", evidence=("source-C",)))
        )
        # Only p3 carries evidence -> only p3 is backed
        assert evidence_backed_arg_ids(trace) == frozenset({"p3"})

    def test_three_agents_one_vote_provides_evidence(self) -> None:
        """A vote with evidence backs the matching Propose, even if the
        Propose itself has no evidence — a coalition witness."""
        trace = (
            Trace()
            .append(_propose("p1", surface="X", agent_id="A", evidence=()))
            .append(_propose("p2", surface="Y", agent_id="B", evidence=()))
            .append(_vote("v1", surface="X", agent_id="C", evidence=("source-C",)))
        )
        # v1 carries evidence and matches p1's surface -> p1 is backed
        assert evidence_backed_arg_ids(trace) == frozenset({"p1"})


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_byte_equal_over_50_invocations(self) -> None:
        trace = (
            Trace()
            .append(_propose("p1", surface="A", evidence=("e1",)))
            .append(_propose("p2", surface="B"))
            .append(_vote("v1", surface="B", evidence=("e2",)))
        )
        first = evidence_backed_arg_ids(trace)
        for _ in range(50):
            assert evidence_backed_arg_ids(trace) == first


# ---------------------------------------------------------------------------
# Other Move types ignored (they don't witness evidence)
# ---------------------------------------------------------------------------


class TestOtherMovesNotWitness:
    """Currently only Propose and Vote can witness evidence; Concede,
    Challenge, Question, etc. do not contribute to evidence backing.

    ADR-0012 documents this scope; future ATL extensions may broaden.
    """

    def test_concede_does_not_witness(self) -> None:
        from council.dialect.moves import Concede

        trace = (
            Trace()
            .append(_propose("p1", surface="X", evidence=()))
            .append(
                Concede(move_id="co1", agent_id="B", round_index=1, target="p1")
            )
        )
        # Even though Concede endorses p1, it doesn't carry evidence atoms
        assert evidence_backed_arg_ids(trace) == frozenset()
