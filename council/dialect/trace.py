"""L0 speech-act algebra — immutable Trace.

Provides O(1)-ish lookup by move_id, round, and force.
The to_events() method is the W1 LTL_f bridge — its schema is frozen after PR3.
"""

from __future__ import annotations

from dataclasses import dataclass

from council.dialect.moves import Challenge, Concede, Force, Move, Propose, Vote


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

        Schema (extended in W1/PR1 — adds has_evidence, has_prior_challenge,
        same_agent_concede_run_ge_3):
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
          has_evidence: bool              — Propose/Vote with non-empty evidence tuple
          has_prior_challenge: bool       — any Challenge precedes this move in the trace
          same_agent_concede_run_ge_3: bool — this and 2 prior same-agent moves are Concede
        """
        force_flags = [f"is_{f.value}" for f in Force]
        result: list[dict[str, object]] = []

        seen_challenge = False
        concede_runs: dict[str, int] = {}  # agent_id → consecutive Concede count

        for m in self.moves:
            event: dict[str, object] = {
                "force": m.force.value,
                "agent_id": m.agent_id,
                "round_index": m.round_index,
            }
            for flag in force_flags:
                force_val = flag[3:]  # strip "is_"
                event[flag] = m.force.value == force_val

            # has_evidence: Propose/Vote with non-empty evidence
            has_evidence: bool = False
            if isinstance(m, Propose):
                has_evidence = len(m.claim.evidence) > 0
            elif isinstance(m, Vote):
                has_evidence = len(m.option.evidence) > 0
            event["has_evidence"] = has_evidence

            # has_prior_challenge: set BEFORE updating for current move
            event["has_prior_challenge"] = seen_challenge
            if isinstance(m, Challenge):
                seen_challenge = True

            # same_agent_concede_run_ge_3: per-agent consecutive concede counter
            agent = m.agent_id
            if isinstance(m, Concede):
                concede_runs[agent] = concede_runs.get(agent, 0) + 1
            else:
                concede_runs[agent] = 0
            event["same_agent_concede_run_ge_3"] = concede_runs.get(agent, 0) >= 3

            result.append(event)

        return tuple(result)
