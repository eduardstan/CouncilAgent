"""Tests for the ATL+CTLK extension to the LTL_f AST + ltlf_to_ctl translator.

Stage 1 / Slice 1.1 of the T7 ATLK revision (specs/t7-atlk-revision.md).
Adds four AST nodes that extend ``LTLf`` and translate to MCMAS-native
ATL+CTLK syntax (manual §3.2.4 grammar, page 18):

  - CoalitionFinally(group, arg)            → ``<group> F translated_arg``
  - CoalitionGlobally(group, arg)           → ``<group> G translated_arg``
  - CoalitionUntil(group, left, right)      → ``<group> (translated_left U translated_right)``
  - Knows(agent, arg)                       → ``K(agent, translated_arg)``

The headline T7 formula
``<<{i}>> F K_i evidence(a, i)`` decomposes as
``CoalitionFinally(group="g_i", arg=Knows(agent="agent_i", arg=Atom("evidence_a_i")))``.
"""

from __future__ import annotations

import dataclasses

import pytest

from council.symbolic.verify.ispl import ltlf_to_ctl
from council.symbolic.verify.ltlf import (
    Atom,
    CoalitionFinally,
    CoalitionGlobally,
    CoalitionUntil,
    Implies,
    Knows,
    LTLf,
    Neg,
    to_spot_str,
)


class TestATLNodesValueSemantics:
    """Frozen+slots dataclass invariants — same as existing LTL_f nodes."""

    def test_coalition_finally_is_frozen(self) -> None:
        node = CoalitionFinally(group="g_alice", arg=Atom("p"))
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.group = "g_bob"  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.arg = Atom("q")  # type: ignore[misc]

    def test_coalition_finally_hashable(self) -> None:
        a = CoalitionFinally(group="g_alice", arg=Atom("p"))
        b = CoalitionFinally(group="g_alice", arg=Atom("p"))
        assert {a, b} == {a}

    def test_coalition_finally_structural_equality(self) -> None:
        a = CoalitionFinally(group="g_alice", arg=Atom("p"))
        b = CoalitionFinally(group="g_alice", arg=Atom("p"))
        c = CoalitionFinally(group="g_bob", arg=Atom("p"))
        assert a == b
        assert a != c

    def test_coalition_globally_is_frozen(self) -> None:
        node = CoalitionGlobally(group="g_alice", arg=Atom("p"))
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.group = "g_bob"  # type: ignore[misc]

    def test_coalition_until_is_frozen(self) -> None:
        node = CoalitionUntil(group="g_alice", left=Atom("p"), right=Atom("q"))
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.left = Atom("r")  # type: ignore[misc]

    def test_knows_is_frozen(self) -> None:
        node = Knows(agent="agent_alice", arg=Atom("p"))
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.agent = "agent_bob"  # type: ignore[misc]

    def test_all_atl_nodes_extend_LTLf(self) -> None:
        nodes: list[LTLf] = [
            CoalitionFinally(group="g", arg=Atom("p")),
            CoalitionGlobally(group="g", arg=Atom("p")),
            CoalitionUntil(group="g", left=Atom("p"), right=Atom("q")),
            Knows(agent="a", arg=Atom("p")),
        ]
        for n in nodes:
            assert isinstance(n, LTLf)


class TestATLNodesDebugStr:
    """Human-readable string forms — match the existing convention
    (Finally → "F(arg)", Globally → "G(arg)", Until → "(left U right)").
    """

    def test_coalition_finally_str(self) -> None:
        node = CoalitionFinally(group="g_alice", arg=Atom("p"))
        assert str(node) == "<<g_alice>>F(p)"

    def test_coalition_globally_str(self) -> None:
        node = CoalitionGlobally(group="g_alice", arg=Atom("p"))
        assert str(node) == "<<g_alice>>G(p)"

    def test_coalition_until_str(self) -> None:
        node = CoalitionUntil(group="g_alice", left=Atom("p"), right=Atom("q"))
        assert str(node) == "<<g_alice>>(p U q)"

    def test_knows_str(self) -> None:
        node = Knows(agent="agent_alice", arg=Atom("p"))
        assert str(node) == "K_agent_alice(p)"


class TestLtlfToCTLOnATLNodes:
    """Translation to MCMAS-native ATL+CTLK syntax (manual §3.2.4 page 18).

    Grammar reminder:
      - <GroupName> F formula
      - <GroupName> G formula
      - <GroupName>(formula U formula)
      - K(AgentName, formula)
    """

    def test_translate_coalition_finally_atom(self) -> None:
        result = ltlf_to_ctl(CoalitionFinally(group="g_alice", arg=Atom("p")))
        assert result == "<g_alice> F p"

    def test_translate_coalition_globally_atom(self) -> None:
        result = ltlf_to_ctl(CoalitionGlobally(group="g_alice", arg=Atom("p")))
        assert result == "<g_alice> G p"

    def test_translate_coalition_until(self) -> None:
        result = ltlf_to_ctl(
            CoalitionUntil(group="g_alice", left=Atom("p"), right=Atom("q"))
        )
        assert result == "<g_alice> (p U q)"

    def test_translate_knows_atom(self) -> None:
        result = ltlf_to_ctl(Knows(agent="agent_alice", arg=Atom("p")))
        assert result == "K(agent_alice, p)"

    def test_translate_t7_headline_pattern(self) -> None:
        # The canonical T7 form: <<{alice}>> F K_alice evidence(p1, alice).
        # Reads "agent alice has a uniform strategy under -atlk 2 to come
        # to know that there exists evidence for argument p1 produced by
        # alice herself" (specs/t7-atlk-revision.md §"The math").
        formula = CoalitionFinally(
            group="g_alice",
            arg=Knows(agent="agent_alice", arg=Atom("evidence_p1_alice")),
        )
        assert ltlf_to_ctl(formula) == "<g_alice> F K(agent_alice, evidence_p1_alice)"

    def test_translate_negation_of_coalition(self) -> None:
        # ¬⟨⟨{i}⟩⟩F p — the negative form used in T7's no-go statement.
        formula = Neg(arg=CoalitionFinally(group="g_alice", arg=Atom("p")))
        assert ltlf_to_ctl(formula) == "!<g_alice> F p"

    def test_translate_coalition_of_negation(self) -> None:
        formula = CoalitionFinally(group="g_alice", arg=Neg(arg=Atom("p")))
        assert ltlf_to_ctl(formula) == "<g_alice> F !p"

    def test_translate_implies_with_coalition(self) -> None:
        # consensus → ⟨⟨{alice}⟩⟩ F evidence — the bible's "if consensus,
        # some agent must have a witness strategy" pattern.
        formula = Implies(
            left=Atom("consensus"),
            right=CoalitionFinally(group="g_alice", arg=Atom("evidence")),
        )
        assert ltlf_to_ctl(formula) == "(consensus -> <g_alice> F evidence)"


class TestSPOTRendererRejectsATL:
    """SPOT (LTL-only) cannot render ATL or epistemic operators —
    the existing ``case _: raise ValueError`` fallback in to_spot_str
    must fire.
    """

    def test_to_spot_str_rejects_coalition_finally(self) -> None:
        with pytest.raises(ValueError, match="Unknown LTLf node"):
            to_spot_str(CoalitionFinally(group="g", arg=Atom("p")))

    def test_to_spot_str_rejects_coalition_globally(self) -> None:
        with pytest.raises(ValueError, match="Unknown LTLf node"):
            to_spot_str(CoalitionGlobally(group="g", arg=Atom("p")))

    def test_to_spot_str_rejects_coalition_until(self) -> None:
        with pytest.raises(ValueError, match="Unknown LTLf node"):
            to_spot_str(CoalitionUntil(group="g", left=Atom("p"), right=Atom("q")))

    def test_to_spot_str_rejects_knows(self) -> None:
        with pytest.raises(ValueError, match="Unknown LTLf node"):
            to_spot_str(Knows(agent="a", arg=Atom("p")))
