"""DeliberationAutomaton — Walton (2010) deliberation dialogue protocol.

States:
  open  → agents may Propose, Challenge, Concede, Question, Clarify
  vote  → agents may Vote or Abstain
  closed → terminal

Transition logic:
  open → vote  after `max_phases` rounds of Propose moves from all agents
  vote → closed after all agents have voted (Vote or Abstain)
"""

from __future__ import annotations

from council.dialect.moves import Force
from council.dialect.protocols.base import ProtocolAutomaton
from council.dialect.trace import Trace

_OPEN_FORCES = frozenset({
    Force.PROPOSE,
    Force.CHALLENGE,
    Force.CONCEDE,
    Force.RETRACT,
    Force.QUESTION,
    Force.CLARIFY,
    Force.PASS,
})

_VOTE_FORCES = frozenset({
    Force.VOTE,
    Force.ABSTAIN,
})


class DeliberationAutomaton(ProtocolAutomaton):
    """Deliberation dialogue protocol with configurable deliberation phases."""

    def __init__(self, *, max_phases: int = 2, agents: list[str]) -> None:
        self._max_phases = max_phases
        self._agents = frozenset(agents)
        self._n = len(agents)

    def _propose_count(self, trace: Trace) -> int:
        return len(trace.by_force(Force.PROPOSE))

    def _vote_count(self, trace: Trace) -> int:
        return len(trace.by_force(Force.VOTE)) + len(trace.by_force(Force.ABSTAIN))

    def _in_vote_phase(self, trace: Trace) -> bool:
        return self._propose_count(trace) >= self._max_phases * self._n

    def state(self, trace: Trace) -> tuple[str, str]:
        if self.is_terminal(trace):
            return ("closed", "terminal")
        if self._in_vote_phase(trace):
            return ("vote", "answer")
        return ("open", "deliberation")

    def legal_forces(self, trace: Trace, agent_id: str) -> frozenset[Force]:
        if self.is_terminal(trace):
            return frozenset()
        if self._in_vote_phase(trace):
            return _VOTE_FORCES
        return _OPEN_FORCES

    def is_terminal(self, trace: Trace) -> bool:
        return (
            self._in_vote_phase(trace)
            and self._vote_count(trace) >= self._n
        )

    def is_answer_phase(self, trace: Trace) -> bool:
        return self._in_vote_phase(trace) and not self.is_terminal(trace)
