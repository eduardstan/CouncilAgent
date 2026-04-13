"""Shared vocabulary for the CouncilAgent pipeline.

This module is the single source of truth for all dataclasses and enums that
cross layer boundaries. Every layer module imports from here; none import from
each other (Constitution §3, architecture.md).

Zero imports from the rest of the council package — this module is the base.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum


class CommunicationMode(StrEnum):
    """How agents receive each other's messages in a given topology."""

    INDIVIDUAL = "individual"  # labeled per-sender messages
    BROADCAST = "broadcast"  # shared board / wiki visible to all
    RELAY = "relay"  # sequential pass-through (ring, star hub)


@dataclass(frozen=True, slots=True)
class AgentResponse:
    """Immutable record of one agent's output for one round."""

    agent_id: str
    content: str
    round_index: int
    tokens_in: int
    tokens_out: int
    cost: float
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VisibilityContext:
    """What a single agent is allowed to see when building its next prompt.

    Constructed exclusively by core._build_visibility_context(), which handles
    adjacency filtering and anonymization. Protocols receive this and trust it;
    they must not re-filter or re-anonymize (Constitution §3, §10).

    The adjacency matrix is NOT present here — it is resolved to filtered lists
    before this object is created.
    """

    agent_id: str
    round_index: int
    visible_responses: list[AgentResponse]
    own_previous_responses: list[AgentResponse]
    total_agents: int
    communication_mode: CommunicationMode
    original_prompt: str


class AnswerNormalizer(ABC):
    """Convert a raw LLM response string to a canonical, comparable form.

    Defined here (not in normalizer.py) so that aggregation.py can depend on this
    ABC without importing a peer layer module (Constitution §3, architecture.md).
    Concrete implementations live in council/normalizer.py.
    """

    @abstractmethod
    async def normalize(self, response: str) -> str: ...


@dataclass(frozen=True, slots=True)
class PreferenceData:
    """Base preference record returned by a Ranking — always produced, even on parse failure.

    Defined here (not in ranking.py) so that aggregation.py can reference it without
    importing a peer layer module (Constitution §3).
    Concrete subclasses live in council/ranking.py.
    """

    raw_text: str = ""


@dataclass(frozen=True, slots=True)
class RichPreference(PreferenceData):
    """Fully parsed preference with ordering, scores, and optional reasoning."""

    ordered_ids: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    reasoning: str = ""


@dataclass(frozen=True, slots=True)
class AggregationResult:
    """Immutable output of an Aggregation layer call."""

    final_answer: str
    confidence: float
    method: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class CouncilState:
    """Mutable accumulator threaded through the pipeline stages.

    Only core.py mutates this; all layer modules receive read-only views via
    VisibilityContext or direct field access where needed (e.g. termination).
    """

    question: str
    round_history: list[AgentResponse] = field(default_factory=list)
    current_round: int = 0
    total_cost: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    termination_reason: str = ""
    final_result: AggregationResult | None = None
    interim_result: AggregationResult | None = None

    @classmethod
    def initial(cls, question: str) -> CouncilState:
        return cls(question=question)


@dataclass(frozen=True, slots=True)
class CouncilResult:
    """Immutable result returned from run_council() to callers."""

    final_answer: str
    confidence: float
    method: str
    rounds_used: int
    total_cost: float
    tokens_in: int
    tokens_out: int
    termination_reason: str
    round_history: list[AgentResponse]
