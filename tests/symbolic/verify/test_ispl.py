"""Tests for council/symbolic/verify/ispl.py — ISPL emitter for MCMAS."""

import pytest

from council.dialect.moves import Challenge, Claim, Concede, Propose, Vote
from council.dialect.trace import Trace
from council.symbolic.verify.ispl import ltlf_to_ctl, trace_to_ispl
from council.symbolic.verify.ltlf import parse

# ---------------------------------------------------------------------------
# ltlf_to_ctl translation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("formula_str", "expected_ctl"), [
    ("p", "p"),
    ("!p", "!p"),
    ("p && q", "(p and q)"),
    ("p || q", "(p or q)"),
    ("p -> q", "(p -> q)"),
    ("F(p)", "EF(p)"),
    ("G(p)", "AG(p)"),
    ("X(p)", "EX(p)"),
    ("p U q", "E(p U q)"),
    ("G(is_vote -> has_evidence)", "AG((is_vote -> has_evidence))"),
    ("F(is_challenge && F(is_vote))", "EF((is_challenge and EF(is_vote)))"),
])
def test_ltlf_to_ctl(formula_str: str, expected_ctl: str) -> None:
    assert ltlf_to_ctl(parse(formula_str)) == expected_ctl


def test_ltlf_to_ctl_boolean_constants() -> None:
    from council.symbolic.verify.ltlf import Boolean
    assert ltlf_to_ctl(Boolean(value=True)) == "true"
    assert ltlf_to_ctl(Boolean(value=False)) == "false"


# ---------------------------------------------------------------------------
# trace_to_ispl — structural tests on a 4-agent / 4-round example
# ---------------------------------------------------------------------------

def _make_4_agent_4_round_trace() -> Trace:
    """Reference trace for the W1 acceptance criterion (master plan §7).

    1 Propose by A (with evidence), 1 Challenge by B, 1 Concede by C, 1 Vote
    by D (with evidence). Spread across 2 rounds.
    """
    t = Trace()
    t = t.append(Propose(move_id="p0", agent_id="A", round_index=0,
                         claim=Claim(surface="x", evidence=("e1",))))
    t = t.append(Challenge(move_id="c1", agent_id="B", round_index=0))
    t = t.append(Concede(move_id="cc2", agent_id="C", round_index=1))
    t = t.append(Vote(move_id="v3", agent_id="D", round_index=1,
                      option=Claim(surface="yes", evidence=("e2",))))
    return t


@pytest.fixture
def trace4() -> Trace:
    return _make_4_agent_4_round_trace()


def test_ispl_contains_required_keywords(trace4: Trace) -> None:
    out = trace_to_ispl(trace4, [parse("F(is_vote)")], agent_ids=("A", "B", "C", "D"))
    for kw in ("Agent Environment", "end Agent", "Vars:", "Actions =",
               "Protocol:", "Evolution:", "Evaluation", "InitStates",
               "Groups", "Formulae"):
        assert kw in out, f"missing keyword {kw!r}"


def test_ispl_has_one_council_agent_per_id(trace4: Trace) -> None:
    out = trace_to_ispl(trace4, [parse("F(is_vote)")], agent_ids=("A", "B", "C", "D"))
    for aid in ("A", "B", "C", "D"):
        assert f"Agent {aid}" in out


def test_ispl_environment_position_range_matches_trace_length(trace4: Trace) -> None:
    out = trace_to_ispl(trace4, [parse("F(is_vote)")], agent_ids=())
    # 4 events → position : 0..4
    assert "position : 0..4;" in out


def test_ispl_evaluation_has_per_position_clauses(trace4: Trace) -> None:
    out = trace_to_ispl(trace4, [parse("F(is_vote)")], agent_ids=())
    # is_propose true at position 0, is_challenge at 1, is_concede at 2, is_vote at 3
    assert "is_propose if Environment.position=0;" in out
    assert "is_challenge if Environment.position=1;" in out
    assert "is_concede if Environment.position=2;" in out
    assert "is_vote if Environment.position=3;" in out


def test_ispl_has_evidence_at_correct_positions(trace4: Trace) -> None:
    """has_evidence should be true at positions 0 (Propose w/ evidence) and 3 (Vote w/ evidence)."""
    out = trace_to_ispl(trace4, [parse("F(is_vote)")], agent_ids=())
    assert "has_evidence if Environment.position=0 or Environment.position=3;" in out


def test_ispl_has_prior_challenge_after_position_1(trace4: Trace) -> None:
    out = trace_to_ispl(trace4, [parse("F(is_vote)")], agent_ids=())
    # Challenge at position 1 → has_prior_challenge true at positions 2 and 3
    assert "has_prior_challenge if Environment.position=2 or Environment.position=3;" in out


def test_ispl_formulae_are_translated_to_ctl(trace4: Trace) -> None:
    out = trace_to_ispl(
        trace4,
        [parse("F(is_vote)"), parse("F(is_challenge && F(is_vote))")],
        agent_ids=(),
    )
    assert "EF(is_vote);" in out
    assert "EF((is_challenge and EF(is_vote)));" in out


def test_ispl_init_states_position_zero(trace4: Trace) -> None:
    out = trace_to_ispl(trace4, [parse("F(is_vote)")], agent_ids=())
    assert "Environment.position=0;" in out


def test_ispl_groups_section_lists_all_agents(trace4: Trace) -> None:
    out = trace_to_ispl(trace4, [parse("F(is_vote)")], agent_ids=("A", "B", "C", "D"))
    assert "council =" in out
    assert "A" in out and "B" in out and "C" in out and "D" in out


def test_ispl_groups_section_empty_when_no_agents(trace4: Trace) -> None:
    out = trace_to_ispl(trace4, [parse("F(is_vote)")], agent_ids=())
    assert "Groups\nend Groups" in out


def test_ispl_empty_trace_produces_valid_skeleton() -> None:
    out = trace_to_ispl(Trace(), [parse("F(p)")], agent_ids=())
    assert "Agent Environment" in out
    assert "position : 0..0;" in out
    assert "trace_empty" in out  # placeholder evaluation


def test_ispl_sanitises_agent_ids() -> None:
    """Agent IDs with special characters are rewritten to valid ISPL identifiers."""
    t = Trace()
    out = trace_to_ispl(t, [], agent_ids=("openrouter/google/gemma:free",))
    # Slashes and colons replaced with underscores
    assert "Agent openrouter_google_gemma_free" in out


def test_ispl_named_property_eventually_decide(trace4: Trace) -> None:
    """The reference master-plan property: F(is_vote) survives encoding."""
    out = trace_to_ispl(trace4, [parse("F(is_vote)")], agent_ids=("A", "B", "C", "D"))
    assert "EF(is_vote);" in out


def test_ispl_named_property_refutation_reachable(trace4: Trace) -> None:
    """The second master-plan property: F(is_challenge && F(is_vote))."""
    out = trace_to_ispl(
        trace4,
        [parse("F(is_challenge && F(is_vote))")],
        agent_ids=("A", "B", "C", "D"),
    )
    assert "EF((is_challenge and EF(is_vote)));" in out


def test_ispl_returns_string_with_trailing_newline(trace4: Trace) -> None:
    out = trace_to_ispl(trace4, [parse("F(is_vote)")], agent_ids=())
    assert out.endswith("\n")
