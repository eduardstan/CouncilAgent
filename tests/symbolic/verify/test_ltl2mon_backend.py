"""Tests for council/symbolic/verify/ltl2mon_backend.py — full LTL_f via progression."""

import pytest

from council.symbolic.verify.ltl2mon_backend import (
    FALSE,
    TRUE,
    ProgressionMonitor,
    progression,
    simplify,
)
from council.symbolic.verify.ltlf import (
    And,
    Atom,
    Boolean,
    Finally,
    Globally,
    Implies,
    Neg,
    Next,
    Or,
    Until,
    parse,
)
from council.symbolic.verify.monitor import LTL3Monitor, PurePythonLTL3Monitor, Verdict

# ---------------------------------------------------------------------------
# simplify() — Boolean identity, complementarity, double-negation
# ---------------------------------------------------------------------------

def test_simplify_neg_true_is_false() -> None:
    assert simplify(Neg(arg=TRUE)) == FALSE


def test_simplify_neg_false_is_true() -> None:
    assert simplify(Neg(arg=FALSE)) == TRUE


def test_simplify_double_negation() -> None:
    assert simplify(Neg(arg=Neg(arg=Atom("p")))) == Atom("p")


def test_simplify_and_with_true_collapses() -> None:
    assert simplify(And(left=TRUE, right=Atom("p"))) == Atom("p")
    assert simplify(And(left=Atom("p"), right=TRUE)) == Atom("p")


def test_simplify_and_with_false_collapses_to_false() -> None:
    assert simplify(And(left=FALSE, right=Atom("p"))) == FALSE
    assert simplify(And(left=Atom("p"), right=FALSE)) == FALSE


def test_simplify_or_with_true_collapses_to_true() -> None:
    assert simplify(Or(left=TRUE, right=Atom("p"))) == TRUE
    assert simplify(Or(left=Atom("p"), right=TRUE)) == TRUE


def test_simplify_or_with_false_collapses() -> None:
    assert simplify(Or(left=FALSE, right=Atom("p"))) == Atom("p")


def test_simplify_idempotent_and() -> None:
    """φ ∧ φ = φ."""
    p = Atom("p")
    assert simplify(And(left=p, right=p)) == p


def test_simplify_idempotent_or() -> None:
    p = Atom("p")
    assert simplify(Or(left=p, right=p)) == p


def test_simplify_complementarity_and() -> None:
    """φ ∧ ¬φ = FALSE."""
    p = Atom("p")
    assert simplify(And(left=p, right=Neg(arg=p))) == FALSE
    assert simplify(And(left=Neg(arg=p), right=p)) == FALSE


def test_simplify_complementarity_or() -> None:
    """phi or not phi = TRUE (excluded middle)."""
    p = Atom("p")
    assert simplify(Or(left=p, right=Neg(arg=p))) == TRUE
    assert simplify(Or(left=Neg(arg=p), right=p)) == TRUE


def test_simplify_implies_unfolds_to_or() -> None:
    p, q = Atom("p"), Atom("q")
    # p -> q is equivalent to (not p) or q after simplification
    result = simplify(Implies(left=p, right=q))
    assert result == Or(left=Neg(arg=p), right=q)


def test_simplify_g_false_is_false() -> None:
    """G(FALSE) = FALSE (the very first event will violate it)."""
    assert simplify(Globally(arg=FALSE)) == FALSE


def test_simplify_until_with_false_right_is_false() -> None:
    """φ U FALSE = FALSE (right side never satisfiable)."""
    assert simplify(Until(left=Atom("p"), right=FALSE)) == FALSE


def test_simplify_until_with_true_right_is_true() -> None:
    """φ U TRUE = TRUE (right side immediately satisfied)."""
    assert simplify(Until(left=Atom("p"), right=TRUE)) == TRUE


# ---------------------------------------------------------------------------
# progression() — Bauer 2010 single-step rules
# ---------------------------------------------------------------------------

def test_progression_atom_true() -> None:
    assert progression(Atom("p"), {"p": True}) == TRUE


def test_progression_atom_false() -> None:
    assert progression(Atom("p"), {"p": False}) == FALSE


def test_progression_neg() -> None:
    assert progression(Neg(arg=Atom("p")), {"p": True}) == FALSE


def test_progression_next_unwraps() -> None:
    """progression(X(φ), e) = φ — X consumes one event, exposes inner φ."""
    p = Atom("p")
    # progression of X(p) gives p (raw); after simplify, still p
    assert progression(Next(arg=p), {"p": False}) == p


def test_progression_finally_residual_keeps_F() -> None:
    """progression(F(p), e) = TRUE if e ⊨ p else F(p)."""
    p = Atom("p")
    # Event with p=False: residual is F(p) (still owed)
    result = progression(Finally(arg=p), {"p": False})
    assert result == Finally(arg=p)
    # Event with p=True: residual is TRUE
    result = progression(Finally(arg=p), {"p": True})
    assert result == TRUE


def test_progression_globally_residual_keeps_G() -> None:
    """progression(G(p), e) = G(p) if e ⊨ p else FALSE."""
    p = Atom("p")
    # Event with p=True: residual is G(p) (still must hold)
    result = progression(Globally(arg=p), {"p": True})
    assert result == Globally(arg=p)
    # Event with p=False: residual is FALSE
    result = progression(Globally(arg=p), {"p": False})
    assert result == FALSE


def test_progression_until_satisfied_immediately() -> None:
    """progression(p U q, e) = TRUE if e ⊨ q."""
    p, q = Atom("p"), Atom("q")
    result = progression(Until(left=p, right=q), {"p": False, "q": True})
    assert result == TRUE


def test_progression_until_violated_immediately() -> None:
    """progression(p U q, e) = FALSE if e ⊭ p ∧ e ⊭ q (both p and q false)."""
    p, q = Atom("p"), Atom("q")
    result = progression(Until(left=p, right=q), {"p": False, "q": False})
    assert result == FALSE


def test_progression_until_pending() -> None:
    """progression(p U q, e) keeps the obligation when only p holds."""
    p, q = Atom("p"), Atom("q")
    result = progression(Until(left=p, right=q), {"p": True, "q": False})
    # Result should still contain p U q (still owed) — not TRUE, not FALSE
    assert result != TRUE
    assert result != FALSE


# ---------------------------------------------------------------------------
# ProgressionMonitor — full LTL_f fragment behaviour
# ---------------------------------------------------------------------------

def test_progression_monitor_atom() -> None:
    """A bare atom: TOP at step 0 if true, BOTTOM if false."""
    m = ProgressionMonitor(parse("p"))
    assert m.step({"p": True}) is Verdict.TOP

    m2 = ProgressionMonitor(parse("p"))
    assert m2.step({"p": False}) is Verdict.BOTTOM


def test_progression_monitor_finally_safety_reachability() -> None:
    """F(p): UNKNOWN until p, then absorbing TOP."""
    m = ProgressionMonitor(parse("F(p)"))
    assert m.step({"p": False}) is Verdict.UNKNOWN
    assert m.step({"p": False}) is Verdict.UNKNOWN
    assert m.step({"p": True}) is Verdict.TOP
    assert m.step({"p": False}) is Verdict.TOP  # absorbing


def test_progression_monitor_globally() -> None:
    """G(p): UNKNOWN while p, BOTTOM on first violation."""
    m = ProgressionMonitor(parse("G(p)"))
    assert m.step({"p": True}) is Verdict.UNKNOWN
    assert m.step({"p": True}) is Verdict.UNKNOWN
    assert m.step({"p": False}) is Verdict.BOTTOM
    assert m.step({"p": True}) is Verdict.BOTTOM  # absorbing


def test_progression_monitor_next() -> None:
    """X(p): UNKNOWN at step 0, TOP/BOTTOM at step 1 based on p."""
    m = ProgressionMonitor(parse("X(p)"))
    assert m.current_verdict is Verdict.UNKNOWN
    assert m.step({"p": False}) is Verdict.UNKNOWN  # X consumed; residual = p
    assert m.step({"p": True}) is Verdict.TOP


def test_progression_monitor_until_satisfaction() -> None:
    """p U q: TOP when q first holds (p was true so far)."""
    m = ProgressionMonitor(parse("p U q"))
    assert m.step({"p": True, "q": False}) is Verdict.UNKNOWN
    assert m.step({"p": True, "q": False}) is Verdict.UNKNOWN
    assert m.step({"p": True, "q": True}) is Verdict.TOP


def test_progression_monitor_until_violation() -> None:
    """p U q: BOTTOM if both p and q false at any step before q."""
    m = ProgressionMonitor(parse("p U q"))
    assert m.step({"p": False, "q": False}) is Verdict.BOTTOM


def test_progression_monitor_weak_until_does_not_violate_on_pf_qf() -> None:
    """p W q: weak until allows p never to hold; only TOP if q satisfies."""
    m = ProgressionMonitor(parse("p W q"))
    assert m.step({"p": True, "q": False}) is Verdict.UNKNOWN
    assert m.step({"p": False, "q": False}) is Verdict.BOTTOM  # p must hold until q


def test_progression_monitor_nested_g_implies_f() -> None:
    """G(p -> F(q)): UNKNOWN through any finite trace (live property)."""
    m = ProgressionMonitor(parse("G(p -> F(q))"))
    assert m.step({"p": False, "q": False}) is Verdict.UNKNOWN
    assert m.step({"p": True, "q": False}) is Verdict.UNKNOWN  # F(q) is owed
    assert m.step({"p": False, "q": True}) is Verdict.UNKNOWN  # F(q) discharged; G continues


def test_progression_monitor_f_g_p() -> None:
    """F(G(p)): a stabilising-eventually-always property."""
    m = ProgressionMonitor(parse("F(G(p))"))
    assert m.step({"p": True}) is Verdict.UNKNOWN
    # No way to reach TOP at runtime (would require certainty over all future)


# ---------------------------------------------------------------------------
# Reset and absorbing semantics
# ---------------------------------------------------------------------------

def test_progression_monitor_reset_restores_unknown() -> None:
    m = ProgressionMonitor(parse("F(p)"))
    m.step({"p": True})
    assert m.current_verdict is Verdict.TOP
    m.reset()
    assert m.current_verdict is Verdict.UNKNOWN
    # Re-run with no satisfaction: stays UNKNOWN
    assert m.step({"p": False}) is Verdict.UNKNOWN


def test_progression_monitor_implements_ltl3monitor_abc() -> None:
    m = ProgressionMonitor(parse("F(p)"))
    assert isinstance(m, LTL3Monitor)


def test_progression_monitor_top_is_absorbing() -> None:
    m = ProgressionMonitor(parse("F(p)"))
    m.step({"p": True})
    assert m.current_verdict is Verdict.TOP
    # Even with a "violating" event, stays TOP
    assert m.step({"p": False}) is Verdict.TOP


def test_progression_monitor_bottom_is_absorbing() -> None:
    m = ProgressionMonitor(parse("G(p)"))
    m.step({"p": False})
    assert m.current_verdict is Verdict.BOTTOM
    # Even with a "satisfying" event, stays BOTTOM
    assert m.step({"p": True}) is Verdict.BOTTOM


# ---------------------------------------------------------------------------
# Cross-validation with PurePythonLTL3Monitor on safety+reachability fragment
# ---------------------------------------------------------------------------

# (formula, list of events) pairs covering the shared fragment.
_CROSSVAL_CASES = [
    # F(p) traces
    ("F(p)", [{"p": False}, {"p": False}, {"p": True}, {"p": False}]),
    ("F(p)", [{"p": False}, {"p": False}, {"p": False}]),  # never True → both UNKNOWN throughout
    # G(p) traces
    ("G(p)", [{"p": True}, {"p": True}, {"p": False}]),
    ("G(p)", [{"p": True}, {"p": True}, {"p": True}]),  # never violated → both UNKNOWN throughout
    # G(!q) traces
    ("G(!q)", [{"q": False}, {"q": True}]),
    # G(p) && F(q) — both monitors must agree at every step
    ("G(p) && F(q)", [{"p": True, "q": False}, {"p": True, "q": True}]),
    ("G(p) && F(q)", [{"p": False, "q": True}]),  # G violated → BOTTOM in both
    # F(p) || G(q)
    ("F(p) || G(q)", [{"p": True, "q": True}]),  # F satisfied → TOP in both
    ("F(p) || G(q)", [{"p": False, "q": True}, {"p": True, "q": True}]),
    # Propositional
    ("p && q", [{"p": True, "q": True}]),
    ("p || q", [{"p": False, "q": False}]),
]


@pytest.mark.parametrize(("formula_str", "events"), _CROSSVAL_CASES)
def test_cross_validate_with_pure_python(
    formula_str: str, events: list[dict[str, object]],
) -> None:
    """ProgressionMonitor and PurePythonLTL3Monitor must agree at every step on the
    safety+reachability fragment."""
    pm = ProgressionMonitor(parse(formula_str))
    pp = PurePythonLTL3Monitor(parse(formula_str))
    for e in events:
        v_prog = pm.step(e)
        v_pure = pp.step(e)
        assert v_prog is v_pure, (
            f"divergence on {formula_str!r} at event {e}: progression={v_prog}, pure={v_pure}"
        )


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

def test_module_constants_are_boolean_instances() -> None:
    assert Boolean(value=True) == TRUE
    assert Boolean(value=False) == FALSE
