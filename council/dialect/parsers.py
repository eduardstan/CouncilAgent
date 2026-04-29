"""L0 — LLM output → Move parser.

Primary path: expects a JSON object (or JSON array of objects) with "force" key.
Fallback path: on JSONDecodeError or unknown force, returns a Propose with
  domain=ClaimDomain.FREE and evidence tagged tier="argument-mining-fallback"
  (Constitution §4 — AgentResponse.move is never None).
"""

from __future__ import annotations

import json
import logging
import uuid

from council.dialect.moves import (
    Abstain,
    Challenge,
    Claim,
    ClaimDomain,
    Clarify,
    Concede,
    Force,
    Move,
    Propose,
    Question,
    Retract,
    Vote,
)

logger = logging.getLogger(__name__)

FALLBACK_TIER = "argument-mining-fallback"


def _make_fallback(agent_id: str, round_index: int, move_id: str, raw: str) -> Propose:
    return Propose(
        move_id=move_id,
        agent_id=agent_id,
        round_index=round_index,
        claim=Claim(
            surface=raw[:200],
            domain=ClaimDomain.FREE,
            evidence=(FALLBACK_TIER,),
        ),
    )


def _parse_single(
    obj: dict[str, object],
    agent_id: str,
    round_index: int,
    move_id: str,
) -> Move:
    force_str = str(obj.get("force", "")).lower()
    try:
        force = Force(force_str)
    except ValueError:
        return _make_fallback(agent_id, round_index, move_id, str(obj))

    match force:
        case Force.PROPOSE:
            return Propose(
                move_id=move_id,
                agent_id=agent_id,
                round_index=round_index,
                claim=Claim(
                    surface=str(obj.get("claim_surface", "")),
                    domain=ClaimDomain(str(obj.get("claim_domain", "free"))),
                ),
                confidence=float(obj.get("confidence", 0.5)),
            )
        case Force.CHALLENGE:
            return Challenge(
                move_id=move_id,
                agent_id=agent_id,
                round_index=round_index,
                target=str(obj.get("target", "")),
                reason=Claim(surface=str(obj.get("reason_surface", ""))),
            )
        case Force.CONCEDE:
            return Concede(
                move_id=move_id,
                agent_id=agent_id,
                round_index=round_index,
                target=str(obj.get("target", "")),
            )
        case Force.RETRACT:
            return Retract(
                move_id=move_id,
                agent_id=agent_id,
                round_index=round_index,
                own=str(obj.get("own", "")),
            )
        case Force.QUESTION:
            return Question(
                move_id=move_id,
                agent_id=agent_id,
                round_index=round_index,
                target=str(obj.get("target", "")),
                query=Claim(surface=str(obj.get("query_surface", ""))),
            )
        case Force.CLARIFY:
            return Clarify(
                move_id=move_id,
                agent_id=agent_id,
                round_index=round_index,
                target=str(obj.get("target", "")),
                restated=Claim(surface=str(obj.get("restated_surface", ""))),
            )
        case Force.VOTE:
            return Vote(
                move_id=move_id,
                agent_id=agent_id,
                round_index=round_index,
                option=Claim(surface=str(obj.get("option_surface", ""))),
                confidence=float(obj.get("confidence", 0.5)),
            )
        case Force.ABSTAIN:
            return Abstain(
                move_id=move_id,
                agent_id=agent_id,
                round_index=round_index,
                why=str(obj.get("why", "")),
            )
        case _:
            return _make_fallback(agent_id, round_index, move_id, str(obj))


def parse_move(
    raw: str,
    *,
    agent_id: str,
    round_index: int,
    move_id: str | None = None,
) -> Move:
    """Parse a single Move from an LLM output string.

    Falls back to a FREE Propose tagged with FALLBACK_TIER on any parse error.
    """
    mid = move_id or str(uuid.uuid4())
    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("expected JSON object")
        return _parse_single(obj, agent_id, round_index, mid)
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        logger.debug("parse_move fallback: %s", exc)
        return _make_fallback(agent_id, round_index, mid, raw)


def parse_move_bundle(
    raw: str,
    *,
    agent_id: str,
    round_index: int,
) -> list[Move]:
    """Parse a JSON array of moves; returns at least one fallback Propose."""
    try:
        items = json.loads(raw)
        if not isinstance(items, list) or len(items) == 0:
            raise ValueError("empty or non-list")
        return [
            _parse_single(item, agent_id, round_index, str(uuid.uuid4()))
            if isinstance(item, dict)
            else _make_fallback(agent_id, round_index, str(uuid.uuid4()), str(item))
            for item in items
        ]
    except (json.JSONDecodeError, ValueError) as exc:
        logger.debug("parse_move_bundle fallback: %s", exc)
        return [_make_fallback(agent_id, round_index, str(uuid.uuid4()), raw)]
