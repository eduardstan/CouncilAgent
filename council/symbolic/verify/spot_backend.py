"""L1 verification — SPOT-backed LTL3 monitor (optional `[verify]` extra).

SPOT (https://spot.lre.epita.fr) is the reference automata-theoretic LTL toolkit.
When available, we delegate formula-to-DFA compilation to SPOT and run the
canonical Bauer-Leucker-Schallhart 2011 dual-DFA LTL3 monitor (one automaton for
phi, one for !phi; verdict at any prefix = the emptiness pattern of their
languages from the current state).

When SPOT is not installed, the import is guarded and `make_monitor()` falls
back to the pure-Python `ProgressionMonitor` (`ltl2mon_backend.py`) which
covers the full LTL_f fragment.

Installation: see `docs/install_spot.md`. SPOT is NOT a pip dependency; it is
installed as a Debian apt package (lre.epita.fr repo) or built from source.
The PyPI package named "spot" is unrelated.

Constitution §8 invariant: `import spot` must be guarded so the no-extras
path always works.
"""

from __future__ import annotations

import logging

from council.symbolic.verify.ltl2mon_backend import ProgressionMonitor
from council.symbolic.verify.ltlf import LTLf, to_spot_str
from council.symbolic.verify.monitor import LTL3Monitor, Verdict

logger = logging.getLogger(__name__)

try:
    import buddy as _buddy  # type: ignore[import-untyped]  # SPOT's BDD library, installed alongside spot
    import spot as _spot  # optional [verify] extra; runtime-checked
    _SPOT_AVAILABLE = True
except ImportError:
    _SPOT_AVAILABLE = False


def is_spot_available() -> bool:
    """True iff the SPOT Python bindings are importable in this environment."""
    return _SPOT_AVAILABLE


# ---------------------------------------------------------------------------
# SPOTMonitor — Bauer 2011 dual-DFA LTL3 monitor
# ---------------------------------------------------------------------------

class SPOTMonitor(LTL3Monitor):
    """LTL3 monitor backed by SPOT's deterministic automata.

    Implements the Bauer-Leucker-Schallhart 2011 dual-DFA construction:
      - aut_phi    = automaton accepting the language of phi
      - aut_neg    = automaton accepting the language of !phi

    At each step, both automata are advanced on the event valuation. The
    verdict at the resulting state pair is:
      - BOTTOM if the language of aut_phi from the current phi-state is empty
        (no extension can satisfy phi)
      - TOP    if the language of aut_neg from the current neg-state is empty
        (no extension can violate phi, equivalently phi is universally satisfied)
      - UNKNOWN otherwise

    Construction raises ImportError if SPOT is not installed; callers should
    use make_monitor() which selects the appropriate backend automatically.
    """

    def __init__(self, formula: LTLf) -> None:
        if not _SPOT_AVAILABLE:
            raise ImportError(
                "SPOT Python bindings are not installed. "
                "See docs/install_spot.md, or use make_monitor(prefer_spot=False) "
                "to fall back to ProgressionMonitor.",
            )
        spot_formula_str = to_spot_str(formula)
        # Build phi-automaton and (!phi)-automaton, both deterministic.
        self._aut_phi = _spot.translate(spot_formula_str, "BA", "deterministic")
        self._aut_neg = _spot.translate(f"!({spot_formula_str})", "BA", "deterministic")
        self._phi_state = int(self._aut_phi.get_init_state_number())
        self._neg_state = int(self._aut_neg.get_init_state_number())
        # Cache initial state numbers for reset()
        self._init_phi = self._phi_state
        self._init_neg = self._neg_state
        # Compute initial verdict
        self._verdict = self._compute_verdict()

    def step(self, event: dict[str, object]) -> Verdict:
        if self._verdict is not Verdict.UNKNOWN:
            return self._verdict  # absorbing
        # Step both automata. If aut_phi has no matching transition the
        # phi-language is empty from this point → BOTTOM. Symmetrically for
        # aut_neg → TOP.
        next_phi = self._next_state(self._aut_phi, self._phi_state, event)
        next_neg = self._next_state(self._aut_neg, self._neg_state, event)
        if next_phi is None:
            self._verdict = Verdict.BOTTOM
            return self._verdict
        if next_neg is None:
            self._verdict = Verdict.TOP
            return self._verdict
        self._phi_state = next_phi
        self._neg_state = next_neg
        self._verdict = self._compute_verdict()
        return self._verdict

    def reset(self) -> None:
        self._phi_state = self._init_phi
        self._neg_state = self._init_neg
        self._aut_phi.set_init_state(self._init_phi)
        self._aut_neg.set_init_state(self._init_neg)
        self._verdict = self._compute_verdict()

    @property
    def current_verdict(self) -> Verdict:
        return self._verdict

    # --- internals --------------------------------------------------------

    @staticmethod
    def _build_event_bdd(automaton: object, event: dict[str, object]) -> object:
        """Build a BDD that is the conjunction of (ap or !ap) per atomic prop in `automaton`,
        according to the truth value in `event` (missing keys default to False).
        """
        bdd_dict = automaton.get_dict()  # type: ignore[attr-defined]
        result = _buddy.bddtrue
        for ap in automaton.ap():  # type: ignore[attr-defined]
            ap_name = ap.ap_name()
            ap_bdd = _spot.formula_to_bdd(ap, bdd_dict, automaton)
            result = result & ap_bdd if bool(event.get(ap_name, False)) else result & -ap_bdd
        return result

    def _next_state(
        self,
        automaton: object,
        state: int,
        event: dict[str, object],
    ) -> int | None:
        """Find the unique transition out of `state` whose label is satisfied by `event`.

        Returns None if no transition matches — this means the automaton's
        language from `state` does not include any extension starting with
        `event`, equivalent to the automaton being empty from that state.
        """
        event_bdd = self._build_event_bdd(automaton, event)
        for edge in automaton.out(state):  # type: ignore[attr-defined]
            if (edge.cond & event_bdd) != _buddy.bddfalse:
                return int(edge.dst)
        return None

    def _compute_verdict(self) -> Verdict:
        """Bauer 2011 verdict via emptiness of phi-language and neg-phi-language
        from the current state pair.
        """
        # BOTTOM check: language of aut_phi from phi_state empty?
        self._aut_phi.set_init_state(self._phi_state)
        if self._aut_phi.is_empty():
            return Verdict.BOTTOM
        # TOP check: language of aut_neg from neg_state empty? (i.e. !phi is unsatisfiable
        # from the current observed prefix → phi is universally satisfied → TOP)
        self._aut_neg.set_init_state(self._neg_state)
        if self._aut_neg.is_empty():
            return Verdict.TOP
        return Verdict.UNKNOWN


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
