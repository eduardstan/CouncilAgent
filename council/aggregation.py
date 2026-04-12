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

from council.context import AgentResponse, AggregationResult, AnswerNormalizer, PreferenceData, RichPreference

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
    final_answer is the winning canonical form (Issue 3 ground truth).

    Constitution §4: normalisation is delegated to AnswerNormalizer —
    never raw Counter on LLM output.
    """

    def __init__(self, normalizer: AnswerNormalizer) -> None:
        self._normalizer = normalizer

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
    """Ordinal aggregation via Borda count.

    Each RichPreference.ordered_ids list contributes N-1 points to rank-1,
    N-2 to rank-2, …, 0 to rank-N (N = number of responses).
    Winner = agent with the highest total points.
    Confidence = winner_score / max_possible_score (bounded [0, 1]).
    """

    async def aggregate(
        self,
        responses: list[AgentResponse],
        preferences: list[PreferenceData] | None = None,
    ) -> AggregationResult:
        if not responses or not preferences:
            return AggregationResult(final_answer="", confidence=0.0, method="BordaCount")

        rich = [p for p in preferences if isinstance(p, RichPreference) and p.ordered_ids]
        if not rich:
            return AggregationResult(final_answer="", confidence=0.0, method="BordaCount")

        n = len(responses)
        scores: dict[str, float] = {r.agent_id: 0.0 for r in responses}

        for pref in rich:
            for rank, agent_id in enumerate(pref.ordered_ids):
                if agent_id in scores:
                    scores[agent_id] += n - 1 - rank

        winner_id = max(scores, key=lambda k: scores[k])
        winner_score = scores[winner_id]
        max_possible = len(rich) * (n - 1)
        confidence = winner_score / max_possible if max_possible > 0 else 0.0

        content_map = {r.agent_id: r.content for r in responses}
        return AggregationResult(
            final_answer=content_map.get(winner_id, ""),
            confidence=confidence,
            method="BordaCount",
        )


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
