"""L0 — Move → natural language renderer.

Domain-conditioned, anonymisation-aware. No model calls.
"""

from __future__ import annotations

from council.dialect.moves import (
    Abstain,
    Challenge,
    Clarify,
    Concede,
    Move,
    Propose,
    Question,
    Retract,
    Vote,
)


def render_move(move: Move, *, anonymize: bool = False) -> str:
    """Render a Move to a natural-language string suitable for prompt injection."""
    agent = "[AGENT]" if anonymize else move.agent_id

    match move:
        case Propose(claim=claim, confidence=conf):
            surface = claim.surface or "(no claim)"
            return f"{agent} proposes: {surface} (confidence={conf:.2f})"

        case Challenge(target=tgt, reason=reason):
            r = reason.surface or "(no reason given)"
            return f"{agent} challenges {tgt}: {r}"

        case Concede(target=tgt):
            return f"{agent} concedes to {tgt}."

        case Retract(own=own, why=why):
            reason = f" ({why.surface})" if why else ""
            return f"{agent} retracts {own}{reason}."

        case Question(target=tgt, query=q):
            qtext = q.surface or "(no question)"
            return f"{agent} asks {tgt}: {qtext}"

        case Clarify(target=tgt, restated=r):
            rtext = r.surface or "(no clarification)"
            return f"{agent} clarifies {tgt}: {rtext}"

        case Vote(option=opt, confidence=conf):
            otext = opt.surface or "(no option)"
            return f"{agent} votes for: {otext} (confidence={conf:.2f})"

        case Abstain(why=why):
            w = f": {why}" if why else ""
            return f"{agent} abstains{w}."
