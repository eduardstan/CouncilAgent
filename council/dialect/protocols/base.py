"""L0 — ProtocolAutomaton abstract base class.

Every dialogue protocol is a typed finite-state machine over speech acts.
Concrete subclasses implement the four required predicates; core.py uses
only these predicates (never round-parity arithmetic).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from council.dialect.moves import Force
from council.dialect.trace import Trace


class ProtocolAutomaton(ABC):
    """Typed FSM over speech acts (Walton-Krabbe deliberation typology)."""

    @abstractmethod
    def state(self, trace: Trace) -> tuple[str, str]:
        """Return (state_name, phase_name) derived from the trace."""

    @abstractmethod
    def legal_forces(self, trace: Trace, agent_id: str) -> frozenset[Force]:
        """Return the set of admissible Forces for agent_id given the trace."""

    @abstractmethod
    def is_terminal(self, trace: Trace) -> bool:
        """True if no further moves are permitted under this protocol."""

    @abstractmethod
    def is_answer_phase(self, trace: Trace) -> bool:
        """True if the current state is an answer/voting phase.

        core.py uses this instead of round_index % 2 (fixes defect D8).
        """
