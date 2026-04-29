"""CompositeAutomaton — chains multiple ProtocolAutomata in sequence.

Transitions to the next automaton when the current one is terminal.
Useful for multi-phase dialogues (e.g. inquiry phase → deliberation phase).
"""

from __future__ import annotations

from council.dialect.moves import Force
from council.dialect.protocols.base import ProtocolAutomaton
from council.dialect.trace import Trace


class CompositeAutomaton(ProtocolAutomaton):
    """Chains automata in sequence; transitions when each becomes terminal."""

    def __init__(self, stages: list[ProtocolAutomaton]) -> None:
        if not stages:
            raise ValueError("CompositeAutomaton requires at least one stage")
        self._stages = stages

    def _active_index(self, trace: Trace) -> int:
        for i, stage in enumerate(self._stages[:-1]):
            if not stage.is_terminal(trace):
                return i
        return len(self._stages) - 1

    def _active(self, trace: Trace) -> ProtocolAutomaton:
        return self._stages[self._active_index(trace)]

    def state(self, trace: Trace) -> tuple[str, str]:
        idx = self._active_index(trace)
        inner_name, inner_phase = self._active(trace).state(trace)
        return (f"stage{idx}:{inner_name}", inner_phase)

    def legal_forces(self, trace: Trace, agent_id: str) -> frozenset[Force]:
        return self._active(trace).legal_forces(trace, agent_id)

    def is_terminal(self, trace: Trace) -> bool:
        return self._stages[-1].is_terminal(trace)

    def is_answer_phase(self, trace: Trace) -> bool:
        return self._active(trace).is_answer_phase(trace)
