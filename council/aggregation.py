"""Aggregation layer — reduce agent responses to a final answer.

Constitution §3: aggregation reduces only. It must not construct deliberation
prompts, mutate state history, or hardcode a synthesis model.
Constitution §9: one correct MajorityVote first. BordaCount and MetaJudge are
Phase 3 work — stubs raise NotImplementedError.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import Counter

from council.context import AgentResponse, AggregationResult
from council.normalizer import AnswerNormalizer, StructuredOutputNormalizer
from council.ranking import PreferenceData

logger = logging.getLogger(__name__)


class Aggregation(ABC):
    """Reduce a list of agent responses (and optional preferences) to a single answer."""

    @abstractmethod
    async def aggregate(
        self,
        responses: list[AgentResponse],
        preferences: list[PreferenceData] | None = None,
    ) -> AggregationResult: ...


class MajorityVote(Aggregation):
    """Normalise all responses, count canonical forms, return the plurality winner.

    Confidence = winner_count / total_responses.
    Returns the *original* content of the first response that mapped to the
    winning canonical form (not the canonical form itself).

    Constitution §4: normalisation is delegated to AnswerNormalizer —
    never raw Counter on LLM output.
    """

    def __init__(self, normalizer: AnswerNormalizer | None = None) -> None:
        self._normalizer = normalizer or StructuredOutputNormalizer()

    async def aggregate(
        self,
        responses: list[AgentResponse],
        preferences: list[PreferenceData] | None = None,
    ) -> AggregationResult:
        if not responses:
            return AggregationResult(final_answer="", confidence=0.0, method="MajorityVote")

        # Normalise every response — builds (canonical, original_content) pairs.
        pairs: list[tuple[str, str]] = []
        for r in responses:
            canonical = await self._normalizer.normalize(r.content)
            pairs.append((canonical, r.content))

        counts: Counter[str] = Counter(canonical for canonical, _ in pairs)
        winning_canonical, winner_count = counts.most_common(1)[0]
        confidence = winner_count / len(responses)

        # Return the canonical form — all winning responses normalise to the same
        # string, so the canonical form IS the unambiguous answer (Issue 3 ground truth).
        return AggregationResult(
            final_answer=winning_canonical,
            confidence=confidence,
            method="MajorityVote",
        )


class BordaCount(Aggregation):
    """Phase 3 implementation. Stub raises NotImplementedError."""

    async def aggregate(
        self,
        responses: list[AgentResponse],
        preferences: list[PreferenceData] | None = None,
    ) -> AggregationResult:
        raise NotImplementedError("BordaCount is implemented in Phase 3")


class MetaJudge(Aggregation):
    """LLM-based synthesis aggregation. Phase 3 implementation.

    Stub raises NotImplementedError. Implementing here would require a ModelClient
    call inside aggregation, which is architecturally allowed but deferred (§9).
    """

    async def aggregate(
        self,
        responses: list[AgentResponse],
        preferences: list[PreferenceData] | None = None,
    ) -> AggregationResult:
        raise NotImplementedError("MetaJudge is implemented in Phase 3")
