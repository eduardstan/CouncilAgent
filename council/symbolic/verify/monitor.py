"""L1 verification — three-valued LTL3 monitor (Bauer-Leucker-Schallhart 2011).

Defines the public ABCs (LTL3Monitor, Property, Verdict) and PurePythonLTL3Monitor
for the safety+reachability fragment of LTL_f. Operates on event dicts produced by
Trace.to_events() (council/dialect/trace.py).

The full LTL_f fragment via the progression algorithm lives in ltl2mon_backend.py
(PR3); the SPOT-backed monitor lives in spot_backend.py (PR4). Both implement the
LTL3Monitor ABC and are interchangeable through the make_monitor() factory.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import ClassVar

from council.symbolic.verify.ltlf import (
    And,
    Atom,
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

# ---------------------------------------------------------------------------
# Verdict — three-valued LTL3 truth value
# ---------------------------------------------------------------------------

class Verdict(Enum):
    """Three-valued LTL3 verdict.

    TOP    — formula necessarily holds on every infinite extension of the prefix.
    BOTTOM — formula necessarily violated on every infinite extension.
    UNKNOWN — the prefix does not yet determine the formula's truth value.
    """

    TOP = "top"
    BOTTOM = "bottom"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Public ABCs
# ---------------------------------------------------------------------------

class LTL3Monitor(ABC):
    """Three-valued runtime monitor over a stream of atomic-proposition dicts."""

    @abstractmethod
    def step(self, event: dict[str, object]) -> Verdict:
        """Advance the monitor by one event; return the current verdict."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset to the initial state (verdict UNKNOWN, all internal state cleared)."""
        ...

    @property
    @abstractmethod
    def current_verdict(self) -> Verdict:
        """The most recently emitted verdict, or UNKNOWN if no event has been stepped."""
        ...


class Property(ABC):
    """A named, citable LTL_f property with a formula and a compile method.

    Subclasses declare the property name and LTL_f source formula as ClassVar
    fields. compile() returns a fresh LTL3Monitor instance for each call.
    """

    name: ClassVar[str]
    formula: ClassVar[str]

    @abstractmethod
    def compile(self) -> LTL3Monitor:
        """Compile the formula into a runnable LTL3Monitor."""
        ...


# ---------------------------------------------------------------------------
# Internal compiled sub-monitors
# ---------------------------------------------------------------------------

class _Compiled(ABC):
    """Internal compiled monitor for a sub-formula. Not part of the public API."""

    @abstractmethod
    def step(self, event: dict[str, object]) -> Verdict: ...

    @abstractmethod
    def reset(self) -> None: ...


class _PropMonitor(_Compiled):
    """Monitor for a purely propositional sub-formula. Verdict fixed at step 0."""

    def __init__(self, formula: LTLf) -> None:
        self._formula = formula
        self._verdict: Verdict = Verdict.UNKNOWN

    def step(self, event: dict[str, object]) -> Verdict:
        if self._verdict is not Verdict.UNKNOWN:
            return self._verdict
        result = _eval_prop(self._formula, event)
        self._verdict = Verdict.TOP if result else Verdict.BOTTOM
        return self._verdict

    def reset(self) -> None:
        self._verdict = Verdict.UNKNOWN


class _GloballyMonitor(_Compiled):
    """Monitor for G(φ) where φ is propositional. BOTTOM if φ ever false; else UNKNOWN."""

    def __init__(self, body: LTLf) -> None:
        self._body = body
        self._verdict: Verdict = Verdict.UNKNOWN

    def step(self, event: dict[str, object]) -> Verdict:
        if self._verdict is Verdict.BOTTOM:
            return self._verdict
        if not _eval_prop(self._body, event):
            self._verdict = Verdict.BOTTOM
        # G never returns TOP at runtime — would require certainty over all future events.
        return self._verdict

    def reset(self) -> None:
        self._verdict = Verdict.UNKNOWN


class _FinallyMonitor(_Compiled):
    """Monitor for F(φ) where φ is propositional. TOP if φ ever true; else UNKNOWN."""

    def __init__(self, body: LTLf) -> None:
        self._body = body
        self._verdict: Verdict = Verdict.UNKNOWN

    def step(self, event: dict[str, object]) -> Verdict:
        if self._verdict is Verdict.TOP:
            return self._verdict
        if _eval_prop(self._body, event):
            self._verdict = Verdict.TOP
        # F never returns BOTTOM at runtime — an extension could still satisfy it.
        return self._verdict

    def reset(self) -> None:
        self._verdict = Verdict.UNKNOWN


class _AndMonitor(_Compiled):
    """And(left, right): BOTTOM if either child is BOTTOM, TOP if both TOP, else UNKNOWN."""

    def __init__(self, left: _Compiled, right: _Compiled) -> None:
        self._left = left
        self._right = right

    def step(self, event: dict[str, object]) -> Verdict:
        left_v = self._left.step(event)
        right_v = self._right.step(event)
        if left_v is Verdict.BOTTOM or right_v is Verdict.BOTTOM:
            return Verdict.BOTTOM
        if left_v is Verdict.TOP and right_v is Verdict.TOP:
            return Verdict.TOP
        return Verdict.UNKNOWN

    def reset(self) -> None:
        self._left.reset()
        self._right.reset()


class _OrMonitor(_Compiled):
    """Or(left, right): TOP if either child is TOP, BOTTOM if both BOTTOM, else UNKNOWN."""

    def __init__(self, left: _Compiled, right: _Compiled) -> None:
        self._left = left
        self._right = right

    def step(self, event: dict[str, object]) -> Verdict:
        left_v = self._left.step(event)
        right_v = self._right.step(event)
        if left_v is Verdict.TOP or right_v is Verdict.TOP:
            return Verdict.TOP
        if left_v is Verdict.BOTTOM and right_v is Verdict.BOTTOM:
            return Verdict.BOTTOM
        return Verdict.UNKNOWN

    def reset(self) -> None:
        self._left.reset()
        self._right.reset()


# ---------------------------------------------------------------------------
# Compilation and propositional evaluation
# ---------------------------------------------------------------------------

def _is_propositional(formula: LTLf) -> bool:
    """True iff formula contains no temporal operator (X, U, W, F, G)."""
    match formula:
        case Atom():
            return True
        case Neg(arg=a):
            return _is_propositional(a)
        case And(left=l, right=r) | Or(left=l, right=r) | Implies(left=l, right=r):
            return _is_propositional(l) and _is_propositional(r)
        case Next() | Until() | WeakUntil() | Finally() | Globally():
            return False
    return False


def _eval_prop(formula: LTLf, event: dict[str, object]) -> bool:
    """Evaluate a purely propositional LTL_f formula against an event dict.

    Atoms read from the event by name (missing keys default to False).
    Raises ValueError if the formula contains a temporal operator.
    """
    match formula:
        case Atom(name=n):
            return bool(event.get(n, False))
        case Neg(arg=a):
            return not _eval_prop(a, event)
        case And(left=l, right=r):
            return _eval_prop(l, event) and _eval_prop(r, event)
        case Or(left=l, right=r):
            return _eval_prop(l, event) or _eval_prop(r, event)
        case Implies(left=l, right=r):
            return (not _eval_prop(l, event)) or _eval_prop(r, event)
        case _:
            raise ValueError(f"_eval_prop: not a propositional formula: {formula}")


def _compile(formula: LTLf) -> _Compiled:
    """Compile an LTL_f formula in the safety+reachability fragment.

    Allowed shapes (recursively):
      - propositional (Atom, Neg, And, Or, Implies over atoms)
      - G(propositional)
      - F(propositional)
      - And/Or of compiled monitors

    Raises ValueError for X, U, W, or nested temporal operators (use PR3 ProgressionMonitor).
    """
    match formula:
        case Globally(arg=body):
            if not _is_propositional(body):
                raise ValueError(
                    f"PurePythonLTL3Monitor only supports G(propositional); "
                    f"got G({body}). Use ProgressionMonitor (PR3) for nested temporal."
                )
            return _GloballyMonitor(body)
        case Finally(arg=body):
            if not _is_propositional(body):
                raise ValueError(
                    f"PurePythonLTL3Monitor only supports F(propositional); "
                    f"got F({body}). Use ProgressionMonitor (PR3) for nested temporal."
                )
            return _FinallyMonitor(body)
        case And(left=l, right=r):
            return _AndMonitor(_compile(l), _compile(r))
        case Or(left=l, right=r):
            return _OrMonitor(_compile(l), _compile(r))
        case Next() | Until() | WeakUntil():
            raise ValueError(
                f"PurePythonLTL3Monitor does not support {type(formula).__name__}; "
                f"use ProgressionMonitor (PR3) or SPOTMonitor (PR4)."
            )
        case _:
            if _is_propositional(formula):
                return _PropMonitor(formula)
            raise ValueError(
                f"PurePythonLTL3Monitor: unsupported formula shape {formula}"
            )


# ---------------------------------------------------------------------------
# PurePythonLTL3Monitor — public entry point for the safety+reachability fragment
# ---------------------------------------------------------------------------

class PurePythonLTL3Monitor(LTL3Monitor):
    """Pure-Python LTL3 monitor for the safety+reachability fragment of LTL_f.

    Supported formula shapes (recursively):
      - propositional combinations of atoms (with Neg, And, Or, Implies)
      - G(propositional)
      - F(propositional)
      - And/Or of supported monitors

    Unsupported (raises ValueError at construction):
      - X (Next), U (Until), W (WeakUntil)
      - nested temporal operators (G inside F, F inside G, etc.)

    For the unsupported fragment, see ProgressionMonitor (PR3) or SPOTMonitor (PR4).
    """

    def __init__(self, formula: LTLf) -> None:
        self._formula = formula
        self._compiled = _compile(formula)
        self._current: Verdict = Verdict.UNKNOWN

    def step(self, event: dict[str, object]) -> Verdict:
        if self._current is not Verdict.UNKNOWN:
            return self._current  # TOP/BOTTOM are absorbing
        self._current = self._compiled.step(event)
        return self._current

    def reset(self) -> None:
        self._compiled.reset()
        self._current = Verdict.UNKNOWN

    @property
    def current_verdict(self) -> Verdict:
        return self._current
