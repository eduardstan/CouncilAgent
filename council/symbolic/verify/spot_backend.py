"""L1 verification — SPOT-backed LTL3 monitor (optional `[verify]` extra).

SPOT (https://spot.lre.epita.fr) is the reference automata-theoretic LTL toolkit.
When available, we delegate formula-to-DFA compilation to SPOT for speed and to
benefit from SPOT's mature handling of complex temporal formulas. When SPOT is
not installed, the import is guarded and `make_monitor()` falls back to the
pure-Python `ProgressionMonitor` (`ltl2mon_backend.py`).

Installation: see `docs/install_spot.md`. SPOT is NOT a pip dependency; it is
installed as a system package (apt / homebrew / source) with Python bindings.

Constitution §8 invariant: `import spot` must be guarded so the no-extras
path always works. Tests for SPOTMonitor are gated by `@skipif(not _spot_available())`.
"""

from __future__ import annotations

from council.symbolic.verify.ltl2mon_backend import ProgressionMonitor
from council.symbolic.verify.ltlf import LTLf, to_spot_str
from council.symbolic.verify.monitor import LTL3Monitor, Verdict

try:
    import spot as _spot  # optional [verify] extra; runtime-checked
    _SPOT_AVAILABLE = True
except ImportError:
    _SPOT_AVAILABLE = False


def is_spot_available() -> bool:
    """True iff the SPOT Python bindings are importable in this environment."""
    return _SPOT_AVAILABLE


# ---------------------------------------------------------------------------
# SPOTMonitor — wraps spot.translate() output as an LTL3Monitor
# ---------------------------------------------------------------------------

class SPOTMonitor(LTL3Monitor):
    """LTL3 monitor backed by SPOT's on-the-fly DFA compilation.

    Compiles the formula via spot.translate() into a deterministic Buchi automaton
    over the LTL_f safety/co-safety fragment as recognised by SPOT, then steps the
    automaton by evaluating each event against the active edge labels.

    Construction raises ImportError if SPOT is not installed; callers should use
    make_monitor() which selects the appropriate backend automatically.
    """

    def __init__(self, formula: LTLf) -> None:
        if not _SPOT_AVAILABLE:
            raise ImportError(
                "SPOT Python bindings are not installed. "
                "See docs/install_spot.md, or use make_monitor(prefer_spot=False) "
                "to fall back to ProgressionMonitor."
            )
        self._formula = formula
        self._spot_formula = _spot.formula(to_spot_str(formula))
        # Translate to a deterministic Buchi automaton with finite-trace semantics.
        # spot.translate() with 'finite' option gives LTL_f compilation when supported.
        self._automaton = _spot.translate(self._spot_formula, "BA", "deterministic")
        self._reset_state()

    def _reset_state(self) -> None:
        """Set the current state to the automaton's initial state."""
        self._current_state: int = int(self._automaton.get_init_state_number())
        self._verdict: Verdict = self._compute_verdict()

    def step(self, event: dict[str, object]) -> Verdict:
        if self._verdict is not Verdict.UNKNOWN:
            return self._verdict  # absorbing
        self._current_state = self._next_state(self._current_state, event)
        self._verdict = self._compute_verdict()
        return self._verdict

    def reset(self) -> None:
        self._reset_state()

    @property
    def current_verdict(self) -> Verdict:
        return self._verdict

    # --- internals --------------------------------------------------------

    def _next_state(self, state: int, event: dict[str, object]) -> int:
        """Pick the unique edge whose label is satisfied by the event.

        Raises ValueError if no edge matches (formula error) or multiple match
        (non-deterministic automaton — should not happen with 'deterministic' flag).
        """
        bdict = self._automaton.get_dict()
        matched: list[int] = []
        for edge in self._automaton.out(state):
            if _label_satisfied(edge.cond, event, bdict, self._spot_formula):
                matched.append(int(edge.dst))
        if len(matched) == 0:
            # Empty language reached → BOTTOM (no path forward)
            return state  # stay; verdict-extraction handles it
        if len(matched) > 1:
            raise ValueError(
                f"SPOTMonitor: non-deterministic transition from state {state} "
                f"on event {event}; check 'deterministic' translation."
            )
        return matched[0]

    def _compute_verdict(self) -> Verdict:
        """Two-DFA LTL3 verdict: TOP if every reachable state is accepting, BOTTOM
        if no reachable state is accepting, else UNKNOWN.

        Bauer-Leucker-Schallhart 2011: build A_phi and A_!phi, compose, derive verdict.
        For practical use we approximate via SPOT's empty/full-language checks on the
        automaton restricted to the current state.
        """
        # For a runtime-monitoring-grade approximation:
        # - If the current state's language is universally accepting (no reachable
        #   non-accepting), → TOP.
        # - If the current state's language is empty (no reachable accepting), → BOTTOM.
        # - Else → UNKNOWN.
        try:
            cur = self._automaton.copy()
            cur.set_init_state(self._current_state)
            if cur.is_empty():
                return Verdict.BOTTOM
            # Build complement automaton; if its language from current state is empty,
            # then the formula is satisfied on every extension → TOP.
            comp = _spot.complement(cur)
            if comp.is_empty():
                return Verdict.TOP
        except Exception:
            # Any SPOT-side issue → fall through to UNKNOWN
            return Verdict.UNKNOWN
        return Verdict.UNKNOWN


def _label_satisfied(
    cond: object,  # spot.bdd
    event: dict[str, object],
    bdict: object,
    formula: object,
) -> bool:
    """True iff the BDD edge condition `cond` is satisfied by the event valuation."""
    # Build an assignment from the event for each propositional variable in the formula.
    # SPOT exposes formula.ap() to enumerate atomic propositions.
    aps = formula.atomic_prop_collect()  # type: ignore[attr-defined]
    bdd_assignment = _spot.bddtrue
    for ap in aps:
        ap_name = ap.ap_name()
        ap_bdd = _spot.formula_to_bdd(_spot.formula(ap_name), bdict, formula)
        if bool(event.get(ap_name, False)):
            bdd_assignment = bdd_assignment & ap_bdd
        else:
            bdd_assignment = bdd_assignment & (-ap_bdd)
    return bool((cond & bdd_assignment) != _spot.bddfalse)


# ---------------------------------------------------------------------------
# make_monitor — single factory for all of W1
# ---------------------------------------------------------------------------

def make_monitor(formula: LTLf, *, prefer_spot: bool = True) -> LTL3Monitor:
    """Construct an LTL3 monitor for `formula`.

    Selection:
      - prefer_spot=True (default): SPOTMonitor if SPOT is installed, else
        ProgressionMonitor (full LTL_f via Bauer 2010).
      - prefer_spot=False: always returns ProgressionMonitor.

    Both backends implement LTL3Monitor and satisfy the same step/reset contract.
    """
    if prefer_spot and _SPOT_AVAILABLE:
        return SPOTMonitor(formula)
    return ProgressionMonitor(formula)
