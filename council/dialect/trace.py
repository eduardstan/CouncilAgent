"""L0 speech-act algebra — immutable Trace.

Provides O(1)-ish lookup by move_id, round, and force.
The to_events() method is the W1 LTL_f bridge — its schema is frozen after PR3.
"""

from __future__ import annotations

from dataclasses import dataclass

from council.dialect.moves import Force, Move


@dataclass(frozen=True, slots=True)
class Trace:
    """An immutable, append-only sequence of Moves.

    Every mutation returns a new Trace; the original is unchanged.
    """

    moves: tuple[Move, ...] = ()

    def append(self, move: Move) -> Trace:
        return Trace(moves=(*self.moves, move))

    def by_id(self, move_id: str) -> Move:
        for m in self.moves:
            if m.move_id == move_id:
                return m
        raise KeyError(move_id)

    def at_round(self, r: int) -> tuple[Move, ...]:
        return tuple(m for m in self.moves if m.round_index == r)

    def by_force(self, f: Force) -> tuple[Move, ...]:
        return tuple(m for m in self.moves if m.force == f)

    def to_events(self) -> tuple[dict[str, object], ...]:
        """Serialise each Move to the atomic-proposition dict that L1 monitors step over.

        Schema (frozen after W0/PR3 — W1 compiles LTL_f against these keys):
          force: str           — the move's Force value
          agent_id: str
          round_index: int
          is_propose: bool     ─┐
          is_challenge: bool    │ one boolean flag per Force value
          is_concede: bool      │
          is_retract: bool      │
          is_question: bool     │
          is_clarify: bool      │
          is_vote: bool         │
          is_abstain: bool      │
          is_pass: bool        ─┘
        """
        force_flags = [f"is_{f.value}" for f in Force]
        result: list[dict[str, object]] = []
        for m in self.moves:
            event: dict[str, object] = {
                "force": m.force.value,
                "agent_id": m.agent_id,
                "round_index": m.round_index,
            }
            for flag in force_flags:
                force_val = flag[3:]  # strip "is_"
                event[flag] = m.force.value == force_val
            result.append(event)
        return tuple(result)
