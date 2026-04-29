"""Tests for council/symbolic/verify/smv.py — SMV emitter for NuSMV."""

import pytest

from council.dialect.moves import Challenge, Claim, Concede, Propose, Vote
from council.dialect.trace import Trace
from council.symbolic.verify.ltlf import parse
from council.symbolic.verify.smv import trace_to_smv


def _make_4_round_trace() -> Trace:
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
    return _make_4_round_trace()


def test_smv_contains_module_main(trace4: Trace) -> None:
    out = trace_to_smv(trace4, [parse("F(is_vote)")])
    assert "MODULE main" in out


def test_smv_var_section(trace4: Trace) -> None:
    out = trace_to_smv(trace4, [parse("F(is_vote)")])
    assert "VAR" in out
    assert "position : 0..4;" in out


def test_smv_define_section_per_ap(trace4: Trace) -> None:
    out = trace_to_smv(trace4, [parse("F(is_vote)")])
    assert "DEFINE" in out
    assert "is_propose := position in { 0 };" in out
    assert "is_vote := position in { 3 };" in out


def test_smv_assign_section(trace4: Trace) -> None:
    out = trace_to_smv(trace4, [parse("F(is_vote)")])
    assert "init(position) := 0;" in out
    assert "next(position) := case position < 4 :" in out


def test_smv_spec_uses_nusmv_syntax(trace4: Trace) -> None:
    """NuSMV uses & / | not 'and' / 'or'."""
    out = trace_to_smv(trace4, [parse("F(is_challenge && F(is_vote))")])
    assert "EF(is_vote)" in out
    # The And inside translates from 'and' to '&'
    assert "&" in out
    assert " and " not in out  # no MCMAS-style 'and'


def test_smv_unused_aps_become_false(trace4: Trace) -> None:
    """APs that are never True in any event get FALSE in DEFINE."""
    out = trace_to_smv(trace4, [parse("F(is_vote)")])
    assert "is_abstain := FALSE;" in out  # No abstain in our trace


def test_smv_empty_trace_valid_skeleton() -> None:
    out = trace_to_smv(Trace(), [parse("F(p)")])
    assert "MODULE main" in out
    assert "position : 0..0;" in out


def test_smv_returns_string_with_trailing_newline(trace4: Trace) -> None:
    out = trace_to_smv(trace4, [parse("F(is_vote)")])
    assert out.endswith("\n")
