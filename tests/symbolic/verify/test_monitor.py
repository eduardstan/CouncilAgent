"""Tests for council/symbolic/verify/monitor.py — LTL3Monitor + PurePythonLTL3Monitor."""

from typing import ClassVar

import pytest

from council.symbolic.verify.ltlf import parse
from council.symbolic.verify.monitor import (
    LTL3Monitor,
    Property,
    PurePythonLTL3Monitor,
    Verdict,
)

# ---------------------------------------------------------------------------
# Verdict enum
# ---------------------------------------------------------------------------

def test_verdict_enum_has_three_values() -> None:
    assert Verdict.TOP.value == "top"
    assert Verdict.BOTTOM.value == "bottom"
    assert Verdict.UNKNOWN.value == "unknown"
    # Exactly three members
    assert len(list(Verdict)) == 3


# ---------------------------------------------------------------------------
# Propositional formulas — verdict fixed at step 0
# ---------------------------------------------------------------------------

def test_propositional_atom_true_returns_top() -> None:
    m = PurePythonLTL3Monitor(parse("p"))
    assert m.current_verdict is Verdict.UNKNOWN
    assert m.step({"p": True}) is Verdict.TOP


def test_propositional_atom_false_returns_bottom() -> None:
    m = PurePythonLTL3Monitor(parse("p"))
    assert m.step({"p": False}) is Verdict.BOTTOM


def test_propositional_atom_missing_key_treats_as_false() -> None:
    m = PurePythonLTL3Monitor(parse("p"))
    assert m.step({}) is Verdict.BOTTOM


def test_propositional_negation() -> None:
    m = PurePythonLTL3Monitor(parse("!p"))
    assert m.step({"p": False}) is Verdict.TOP


def test_propositional_and() -> None:
    m = PurePythonLTL3Monitor(parse("p && q"))
    assert m.step({"p": True, "q": True}) is Verdict.TOP

    m2 = PurePythonLTL3Monitor(parse("p && q"))
    assert m2.step({"p": True, "q": False}) is Verdict.BOTTOM


def test_propositional_or() -> None:
    m = PurePythonLTL3Monitor(parse("p || q"))
    assert m.step({"p": False, "q": True}) is Verdict.TOP

    m2 = PurePythonLTL3Monitor(parse("p || q"))
    assert m2.step({"p": False, "q": False}) is Verdict.BOTTOM


def test_propositional_implies_vacuous() -> None:
    """p -> q with p=False is vacuously true."""
    m = PurePythonLTL3Monitor(parse("p -> q"))
    assert m.step({"p": False, "q": False}) is Verdict.TOP


def test_propositional_implies_modus_ponens() -> None:
    m = PurePythonLTL3Monitor(parse("p -> q"))
    assert m.step({"p": True, "q": False}) is Verdict.BOTTOM


# ---------------------------------------------------------------------------
# G(propositional) — safety; BOTTOM on first violation; never TOP
# ---------------------------------------------------------------------------

def test_globally_unknown_while_property_holds() -> None:
    m = PurePythonLTL3Monitor(parse("G(p)"))
    assert m.step({"p": True}) is Verdict.UNKNOWN
    assert m.step({"p": True}) is Verdict.UNKNOWN
    assert m.step({"p": True}) is Verdict.UNKNOWN


def test_globally_bottom_on_first_violation() -> None:
    m = PurePythonLTL3Monitor(parse("G(p)"))
    assert m.step({"p": True}) is Verdict.UNKNOWN
    assert m.step({"p": False}) is Verdict.BOTTOM


def test_globally_bottom_is_absorbing() -> None:
    m = PurePythonLTL3Monitor(parse("G(p)"))
    assert m.step({"p": False}) is Verdict.BOTTOM
    # Subsequent events: still BOTTOM regardless of value
    assert m.step({"p": True}) is Verdict.BOTTOM
    assert m.step({"p": True}) is Verdict.BOTTOM


def test_globally_with_negation() -> None:
    """G(!is_concede) — safety: never concede."""
    m = PurePythonLTL3Monitor(parse("G(!is_concede)"))
    assert m.step({"is_concede": False}) is Verdict.UNKNOWN
    assert m.step({"is_concede": True}) is Verdict.BOTTOM


def test_globally_with_implies() -> None:
    """G(p -> q) — every event with p must have q."""
    m = PurePythonLTL3Monitor(parse("G(p -> q)"))
    # p=False vacuously true
    assert m.step({"p": False, "q": False}) is Verdict.UNKNOWN
    # p=True, q=True satisfies
    assert m.step({"p": True, "q": True}) is Verdict.UNKNOWN
    # p=True, q=False violates
    assert m.step({"p": True, "q": False}) is Verdict.BOTTOM


# ---------------------------------------------------------------------------
# F(propositional) — reachability; TOP on first satisfaction; never BOTTOM
# ---------------------------------------------------------------------------

def test_finally_unknown_until_property_holds() -> None:
    m = PurePythonLTL3Monitor(parse("F(p)"))
    assert m.step({"p": False}) is Verdict.UNKNOWN
    assert m.step({"p": False}) is Verdict.UNKNOWN
    assert m.step({"p": False}) is Verdict.UNKNOWN


def test_finally_top_on_first_satisfaction() -> None:
    m = PurePythonLTL3Monitor(parse("F(p)"))
    assert m.step({"p": False}) is Verdict.UNKNOWN
    assert m.step({"p": True}) is Verdict.TOP


def test_finally_top_is_absorbing() -> None:
    m = PurePythonLTL3Monitor(parse("F(p)"))
    assert m.step({"p": True}) is Verdict.TOP
    # Subsequent events: still TOP
    assert m.step({"p": False}) is Verdict.TOP
    assert m.step({"p": False}) is Verdict.TOP


def test_finally_named_property_eventually_decide() -> None:
    """F(is_vote) — the EventuallyDecide property."""
    m = PurePythonLTL3Monitor(parse("F(is_vote)"))
    # Trace with no vote: stays UNKNOWN
    for _ in range(5):
        assert m.step({"is_vote": False}) is Verdict.UNKNOWN
    # First vote → TOP
    assert m.step({"is_vote": True}) is Verdict.TOP


# ---------------------------------------------------------------------------
# And/Or combinations of monitors
# ---------------------------------------------------------------------------

def test_and_combination_g_and_f() -> None:
    """G(p) && F(q) — both must eventually align."""
    m = PurePythonLTL3Monitor(parse("G(p) && F(q)"))
    assert m.step({"p": True, "q": False}) is Verdict.UNKNOWN
    assert m.step({"p": True, "q": True}) is Verdict.UNKNOWN
    # F=TOP, G=UNKNOWN → still UNKNOWN (G could fail later)


def test_and_combination_g_violation_dominates() -> None:
    """G(p) && F(q): G violation → BOTTOM regardless of F."""
    m = PurePythonLTL3Monitor(parse("G(p) && F(q)"))
    assert m.step({"p": False, "q": True}) is Verdict.BOTTOM


def test_or_combination_f_satisfaction_dominates() -> None:
    """F(p) || G(q): F satisfaction → TOP regardless of G."""
    m = PurePythonLTL3Monitor(parse("F(p) || G(q)"))
    assert m.step({"p": True, "q": False}) is Verdict.TOP


def test_or_combination_both_unknown() -> None:
    """F(p) || G(q) — both UNKNOWN means combined UNKNOWN."""
    m = PurePythonLTL3Monitor(parse("F(p) || G(q)"))
    assert m.step({"p": False, "q": True}) is Verdict.UNKNOWN


def test_or_combination_one_bottom_one_unknown_stays_unknown() -> None:
    """F(p) || G(q): G-violated, F-unknown → UNKNOWN (F could still fire)."""
    m = PurePythonLTL3Monitor(parse("F(p) || G(q)"))
    # Step where q=False (G(q) violated) and p=False (F(p) still unknown)
    assert m.step({"p": False, "q": False}) is Verdict.UNKNOWN


# ---------------------------------------------------------------------------
# reset() — restores UNKNOWN and re-runs trace fresh
# ---------------------------------------------------------------------------

def test_reset_restores_unknown_state() -> None:
    m = PurePythonLTL3Monitor(parse("F(p)"))
    m.step({"p": True})
    assert m.current_verdict is Verdict.TOP
    m.reset()
    assert m.current_verdict is Verdict.UNKNOWN


def test_reset_allows_fresh_trace() -> None:
    """After reset, the same monitor should yield the same verdict on a re-run."""
    m = PurePythonLTL3Monitor(parse("G(p)"))
    assert m.step({"p": True}) is Verdict.UNKNOWN
    assert m.step({"p": False}) is Verdict.BOTTOM
    m.reset()
    assert m.step({"p": True}) is Verdict.UNKNOWN
    assert m.step({"p": False}) is Verdict.BOTTOM


def test_reset_propagates_to_combined_monitors() -> None:
    """reset() on outer monitor must reset inner _AndMonitor children."""
    m = PurePythonLTL3Monitor(parse("G(p) && F(q)"))
    m.step({"p": False, "q": True})
    assert m.current_verdict is Verdict.BOTTOM
    m.reset()
    # Now re-run with non-violating events → UNKNOWN, not stuck BOTTOM
    assert m.step({"p": True, "q": False}) is Verdict.UNKNOWN


# ---------------------------------------------------------------------------
# Unsupported formulas raise ValueError at construction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("formula_str", [
    "X(p)",                # Next not supported in PR2
    "p U q",               # Until not supported
    "p W q",               # WeakUntil not supported
    "G(F(p))",             # Nested temporal
    "F(G(p))",             # Nested temporal
    "G(p -> F(q))",        # G wrapping a non-propositional (F inside)
    "F(p && X(q))",        # F wrapping a non-propositional
])
def test_unsupported_formulas_raise_value_error(formula_str: str) -> None:
    with pytest.raises(ValueError, match=r"(?i)unsupported|use ProgressionMonitor|does not support"):
        PurePythonLTL3Monitor(parse(formula_str))


# ---------------------------------------------------------------------------
# Property ABC contract
# ---------------------------------------------------------------------------

def test_property_subclass_compiles_to_monitor() -> None:
    class MyEventuallyDecide(Property):
        name: ClassVar[str] = "MyEventuallyDecide"
        formula: ClassVar[str] = "F(is_vote)"

        def compile(self) -> LTL3Monitor:
            return PurePythonLTL3Monitor(parse(self.formula))

    p = MyEventuallyDecide()
    assert p.name == "MyEventuallyDecide"
    assert p.formula == "F(is_vote)"
    monitor = p.compile()
    assert isinstance(monitor, LTL3Monitor)
    assert monitor.step({"is_vote": True}) is Verdict.TOP


def test_property_compile_returns_fresh_monitor_each_call() -> None:
    """Two compile() calls must produce independent monitor instances."""
    class P(Property):
        name: ClassVar[str] = "P"
        formula: ClassVar[str] = "F(p)"

        def compile(self) -> LTL3Monitor:
            return PurePythonLTL3Monitor(parse(self.formula))

    a = P().compile()
    b = P().compile()
    a.step({"p": True})
    assert a.current_verdict is Verdict.TOP
    assert b.current_verdict is Verdict.UNKNOWN  # b not affected


def test_property_is_abstract() -> None:
    """Property cannot be instantiated directly (abstract base)."""
    with pytest.raises(TypeError):
        Property()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# LTL3Monitor ABC contract — current_verdict matches last step()
# ---------------------------------------------------------------------------

def test_current_verdict_matches_last_step() -> None:
    m = PurePythonLTL3Monitor(parse("F(p)"))
    assert m.current_verdict is Verdict.UNKNOWN
    v = m.step({"p": False})
    assert m.current_verdict is v
    v = m.step({"p": True})
    assert m.current_verdict is v


def test_pure_python_monitor_implements_abc() -> None:
    m = PurePythonLTL3Monitor(parse("F(p)"))
    assert isinstance(m, LTL3Monitor)
