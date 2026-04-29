"""PersuasionAutomaton — Walton (1995) persuasion dialogue.

One agent attempts to persuade others of a claim.
Open phase allows Propose + Challenge/Concede/Retract.
Vote phase after max_rounds rounds.
"""

from __future__ import annotations

from council.dialect.moves import Force
from council.dialect.protocols.base import ProtocolAutomaton
from council.dialect.trace import Trace

_OPEN = frozenset({Force.PROPOSE, Force.CHALLENGE, Force.CONCEDE, Force.RETRACT, Force.PASS})
_VOTE = frozenset({Force.VOTE, Force.ABSTAIN})


class PersuasionAutomaton(ProtocolAutomaton):
    def __init__(self, *, max_rounds: int = 3, agents: list[str]) -> None:
        self._max_rounds = max_rounds
        self._n = len(agents)

    def _rounds_elapsed(self, trace: Trace) -> int:
        if not trace.moves:
            return 0
        return max(m.round_index for m in trace.moves) + 1

    def _in_vote_phase(self, trace: Trace) -> bool:
        return self._rounds_elapsed(trace) >= self._max_rounds

    def state(self, trace: Trace) -> tuple[str, str]:
        if self.is_terminal(trace):
            return ("closed", "terminal")
        if self._in_vote_phase(trace):
            return ("vote", "answer")
        return ("open", "persuasion")

    def legal_forces(self, trace: Trace, agent_id: str) -> frozenset[Force]:
        if self.is_terminal(trace):
            return frozenset()
        return _VOTE if self._in_vote_phase(trace) else _OPEN

    def is_terminal(self, trace: Trace) -> bool:
        vote_abstain = len(trace.by_force(Force.VOTE)) + len(trace.by_force(Force.ABSTAIN))
        return self._in_vote_phase(trace) and vote_abstain >= self._n

    def is_answer_phase(self, trace: Trace) -> bool:
        return self._in_vote_phase(trace) and not self.is_terminal(trace)
