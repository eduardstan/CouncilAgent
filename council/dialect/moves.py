"""L0 speech-act algebra — typed Move ADT.

Defines the complete Move union type and its supporting value objects.
No model calls, no protocol knowledge, no admissibility rules here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Force(StrEnum):
    """The illocutionary force of a speech act."""

    PROPOSE = "propose"
    CHALLENGE = "challenge"
    CONCEDE = "concede"
    RETRACT = "retract"
    QUESTION = "question"
    CLARIFY = "clarify"
    VOTE = "vote"
    ABSTAIN = "abstain"
    PASS = "pass"


class ClaimDomain(StrEnum):
    """Semantic domain of a Claim — determines surface rendering and metrics."""

    FOL = "fol"
    LTLF = "ltlf"
    ARITH = "arith"
    CODE = "code"
    FREE = "free"


@dataclass(frozen=True, slots=True)
class Claim:
    """A propositional claim carried by a Move."""

    surface: str
    formula: str | None = None
    domain: ClaimDomain = ClaimDomain.FREE
    evidence: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Shared header fields for every Move variant.
# Using composition (not inheritance) to stay compatible with slots=True.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Propose:
    move_id: str
    agent_id: str
    round_index: int
    force: Force = Force.PROPOSE
    claim: Claim = field(default_factory=lambda: Claim(surface=""))
    confidence: float = 0.5


@dataclass(frozen=True, slots=True)
class Challenge:
    move_id: str
    agent_id: str
    round_index: int
    force: Force = Force.CHALLENGE
    target: str = ""
    reason: Claim = field(default_factory=lambda: Claim(surface=""))
    confidence: float = 0.5  # Patch C (ADR-0006) — feeds Attack.weight in W2


@dataclass(frozen=True, slots=True)
class Concede:
    move_id: str
    agent_id: str
    round_index: int
    force: Force = Force.CONCEDE
    target: str = ""


@dataclass(frozen=True, slots=True)
class Retract:
    move_id: str
    agent_id: str
    round_index: int
    force: Force = Force.RETRACT
    own: str = ""
    why: Claim | None = None


@dataclass(frozen=True, slots=True)
class Question:
    move_id: str
    agent_id: str
    round_index: int
    force: Force = Force.QUESTION
    target: str = ""
    query: Claim = field(default_factory=lambda: Claim(surface=""))


@dataclass(frozen=True, slots=True)
class Clarify:
    move_id: str
    agent_id: str
    round_index: int
    force: Force = Force.CLARIFY
    target: str = ""
    restated: Claim = field(default_factory=lambda: Claim(surface=""))


@dataclass(frozen=True, slots=True)
class Vote:
    move_id: str
    agent_id: str
    round_index: int
    force: Force = Force.VOTE
    option: Claim = field(default_factory=lambda: Claim(surface=""))
    confidence: float = 0.5


@dataclass(frozen=True, slots=True)
class Abstain:
    move_id: str
    agent_id: str
    round_index: int
    force: Force = Force.ABSTAIN
    why: str = ""


Move = Propose | Challenge | Concede | Retract | Question | Clarify | Vote | Abstain
