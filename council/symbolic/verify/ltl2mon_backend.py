"""L1 verification — pure-Python progression-based LTL3 monitor for full LTL_f.

Implements the Bauer-Leucker-Schallhart 2011 / Bauer 2010 progression algorithm
for finite-trace LTL (LTL_f). Handles the full fragment: atoms, Boolean
combinations, X (Next), F (Finally), G (Globally), U (Until), W (Weak Until),
including arbitrary nesting.

The algorithm maintains the formula as a residual that is rewritten on every
event:

    progression(φ, e) = φ' such that the trace e·w satisfies φ
                                  iff w satisfies φ'

After each step we simplify the residual. If it reduces to TRUE → Verdict.TOP;
if it reduces to FALSE → Verdict.BOTTOM; otherwise UNKNOWN.

Cross-validates with PurePythonLTL3Monitor (monitor.py) on the safety+reachability
fragment. Use this monitor when the formula contains X, U, W, or nested temporal
operators.
"""

from __future__ import annotations

from council.symbolic.verify.ltlf import (
    And,
    Atom,
    Boolean,
    Finally,
    Globally,
    Implies,
    LTLf,
    Neg,
    Next,
    Or,
    Until,
    WeakUntil,
)
from council.symbolic.verify.monitor import LTL3Monitor, Verdict

TRUE: LTLf = Boolean(value=True)
FALSE: LTLf = Boolean(value=False)


# ---------------------------------------------------------------------------
# Simplification — applies identity, complementarity, and double-negation laws
# ---------------------------------------------------------------------------

def _is_true(f: LTLf) -> bool:
    return isinstance(f, Boolean) and f.value


def _is_false(f: LTLf) -> bool:
    return isinstance(f, Boolean) and not f.value


def simplify(formula: LTLf) -> LTLf:
    """Apply Boolean identity laws, complementarity, and double-negation.

    Conservative: detects only structural tautologies/contradictions, not full
    SAT. Sufficient for the LTL3 verdict check where we look for
    formula ≡ TRUE (TOP) or formula ≡ FALSE (BOTTOM).
    """
    match formula:
        case Boolean() | Atom():
            return formula
        case Neg(arg=a):
            sa = simplify(a)
            if _is_true(sa):
                return FALSE
            if _is_false(sa):
                return TRUE
            if isinstance(sa, Neg):  # double negation
                return sa.arg
            return Neg(arg=sa)
        case And(left=lf, right=rf):
            sl = simplify(lf)
            sr = simplify(rf)
            if _is_false(sl) or _is_false(sr):
                return FALSE
            if _is_true(sl):
                return sr
            if _is_true(sr):
                return sl
            if sl == sr:                             # idempotent: φ ∧ φ = φ
                return sl
            if isinstance(sr, Neg) and sr.arg == sl:  # φ ∧ ¬φ = FALSE
                return FALSE
            if isinstance(sl, Neg) and sl.arg == sr:  # ¬φ ∧ φ = FALSE
                return FALSE
            return And(left=sl, right=sr)
        case Or(left=lf, right=rf):
            sl = simplify(lf)
            sr = simplify(rf)
            if _is_true(sl) or _is_true(sr):
                return TRUE
            if _is_false(sl):
                return sr
            if _is_false(sr):
                return sl
            if sl == sr:                             # idempotent
                return sl
            if isinstance(sr, Neg) and sr.arg == sl:  # phi or not phi = TRUE
                return TRUE
            if isinstance(sl, Neg) and sl.arg == sr:
                return TRUE
            return Or(left=sl, right=sr)
        case Implies(left=lf, right=rf):
            # Rewrite as (not left) or right and simplify
            return simplify(Or(left=Neg(arg=lf), right=rf))
        case Next(arg=a):
            return Next(arg=simplify(a))
        case Finally(arg=a):
            sa = simplify(a)
            if _is_true(sa):  # F(TRUE) = TRUE (immediately satisfied)
                return TRUE
            if _is_false(sa):  # F(FALSE) is never satisfied; in LTL3 stays UNKNOWN forever
                return Finally(arg=sa)
            return Finally(arg=sa)
        case Globally(arg=a):
            sa = simplify(a)
            if _is_false(sa):  # G(FALSE) = FALSE
                return FALSE
            return Globally(arg=sa)
        case Until(left=lf, right=rf):
            sl = simplify(lf)
            sr = simplify(rf)
            if _is_true(sr):  # φ U TRUE = TRUE
                return TRUE
            if _is_false(sr):  # φ U FALSE = FALSE (right side never satisfied)
                return FALSE
            return Until(left=sl, right=sr)
        case WeakUntil(left=lf, right=rf):
            sl = simplify(lf)
            sr = simplify(rf)
            if _is_true(sr):  # φ W TRUE = TRUE
                return TRUE
            return WeakUntil(left=sl, right=sr)
    return formula


# ---------------------------------------------------------------------------
# Progression — Bauer 2010
# ---------------------------------------------------------------------------

def progression(formula: LTLf, event: dict[str, object]) -> LTLf:
    """Compute the residual of `formula` after observing `event`.

    Bauer 2010 rules (using ASCII operators: && for and, || for or, ! for not):
      progression(b, e)            = b                                  (Boolean constant)
      progression(p, e)            = TRUE if e |= p else FALSE          (Atom)
      progression(!phi, e)         = !progression(phi, e)
      progression(phi && psi, e)   = progression(phi, e) && progression(psi, e)
      progression(phi || psi, e)   = progression(phi, e) || progression(psi, e)
      progression(phi -> psi, e)   = !progression(phi, e) || progression(psi, e)
      progression(X phi, e)        = phi
      progression(F phi, e)        = progression(phi, e) || F phi
      progression(G phi, e)        = progression(phi, e) && G phi
      progression(phi U psi, e)    = progression(psi, e) || (progression(phi, e) && phi U psi)
      progression(phi W psi, e)    = progression(psi, e) || (progression(phi, e) && phi W psi)

    The result is simplified before return.
    """
    return simplify(_progress(formula, event))


def _progress(formula: LTLf, event: dict[str, object]) -> LTLf:
    """Raw progression rules (returns un-simplified). Use progression() externally."""
    match formula:
        case Boolean():
            return formula
        case Atom(name=n):
            return TRUE if bool(event.get(n, False)) else FALSE
        case Neg(arg=a):
            return Neg(arg=_progress(a, event))
        case And(left=lf, right=rf):
            return And(left=_progress(lf, event), right=_progress(rf, event))
        case Or(left=lf, right=rf):
            return Or(left=_progress(lf, event), right=_progress(rf, event))
        case Implies(left=lf, right=rf):
            return Or(left=Neg(arg=_progress(lf, event)), right=_progress(rf, event))
        case Next(arg=a):
            return a
        case Finally(arg=a):
            return Or(left=_progress(a, event), right=Finally(arg=a))
        case Globally(arg=a):
            return And(left=_progress(a, event), right=Globally(arg=a))
        case Until(left=lf, right=rf):
            return Or(
                left=_progress(rf, event),
                right=And(left=_progress(lf, event), right=Until(left=lf, right=rf)),
            )
        case WeakUntil(left=lf, right=rf):
            return Or(
                left=_progress(rf, event),
                right=And(left=_progress(lf, event), right=WeakUntil(left=lf, right=rf)),
            )
    raise ValueError(f"_progress: unhandled formula {formula!r}")


# ---------------------------------------------------------------------------
# ProgressionMonitor — LTL3Monitor for the full LTL_f fragment
# ---------------------------------------------------------------------------

def _verdict_of(residual: LTLf) -> Verdict:
    """Map a simplified residual to a Verdict."""
    if _is_true(residual):
        return Verdict.TOP
    if _is_false(residual):
        return Verdict.BOTTOM
    return Verdict.UNKNOWN


class ProgressionMonitor(LTL3Monitor):
    """Three-valued LTL3 monitor for the full LTL_f fragment via progression.

    On each step:
      1. Apply the Bauer 2010 progression rules to the current residual.
      2. Simplify with identity / complementarity / double-negation laws.
      3. Emit Verdict.TOP if residual ≡ TRUE, BOTTOM if ≡ FALSE, else UNKNOWN.

    TOP and BOTTOM are absorbing: once reached, subsequent step() calls
    short-circuit and return the cached verdict.
    """

    def __init__(self, formula: LTLf) -> None:
        self._initial = simplify(formula)
        self._residual: LTLf = self._initial
        self._current: Verdict = _verdict_of(self._residual)

    def step(self, event: dict[str, object]) -> Verdict:
        if self._current is not Verdict.UNKNOWN:
            return self._current  # absorbing
        self._residual = progression(self._residual, event)
        self._current = _verdict_of(self._residual)
        return self._current

    def reset(self) -> None:
        self._residual = self._initial
        self._current = _verdict_of(self._residual)

    @property
    def current_verdict(self) -> Verdict:
        return self._current
