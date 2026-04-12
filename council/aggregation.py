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
from council.models import ModelClient, ModelFailure, ModelRequest

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
    """LLM-based synthesis aggregation.

    Sends all agent responses to a synthesis model and returns its output as the
    final answer. The synthesis model and ModelClient are injected at construction
    — never hardcoded (Constitution §3).

    Confidence is fixed at 1.0 because MetaJudge produces one synthesized answer;
    agreement-based confidence lives at the CouncilAgent layer above.
    """

    def __init__(self, model: str, model_client: ModelClient) -> None:
        self._model = model
        self._model_client = model_client

    async def aggregate(
        self,
        responses: list[AgentResponse],
        preferences: list[PreferenceData] | None = None,
    ) -> AggregationResult:
        if not responses:
            return AggregationResult(final_answer="", confidence=0.0, method="MetaJudge")

        formatted = "\n\n".join(
            f"[{r.agent_id}]:\n{r.content}" for r in responses
        )
        prompt = (
            "You are a synthesis judge. Below are responses from multiple agents "
            "to a question. Synthesize them into a single best answer.\n\n"
            f"Responses:\n{formatted}\n\n"
            "Provide your synthesized answer:"
        )
        outcome = await self._model_client.complete(
            ModelRequest(model=self._model, prompt=prompt),
            agent_id="meta-judge",
            round_index=0,
        )
        if isinstance(outcome, ModelFailure):
            logger.warning("MetaJudge model call failed: %s", outcome.error)
            return AggregationResult(final_answer="", confidence=0.0, method="MetaJudge")

        return AggregationResult(
            final_answer=outcome.content,
            confidence=1.0,
            method="MetaJudge",
        )


class CondorcetAggregation(Aggregation):
    """Condorcet/Copeland social-choice aggregation (Issue 13 ground truth).

    Builds a pairwise win matrix from RichPreference.ordered_ids.
    A Condorcet winner beats every other candidate in a majority of preference
    lists. If no Condorcet winner exists (cycle), Copeland's method is used:
    each candidate's score = wins - losses across all pairwise contests.

    Confidence:
    - Condorcet: min pairwise win-ratio (weakest majority the winner holds).
    - Copeland: (copeland_score + max_wins) / (2 * max_wins), normalized to [0, 1].
    """

    async def aggregate(
        self,
        responses: list[AgentResponse],
        preferences: list[PreferenceData] | None = None,
    ) -> AggregationResult:
        if not responses or not preferences:
            return AggregationResult(final_answer="", confidence=0.0, method="Condorcet")

        rich = [p for p in preferences if isinstance(p, RichPreference) and p.ordered_ids]
        if not rich:
            return AggregationResult(final_answer="", confidence=0.0, method="Condorcet")

        agent_ids = [r.agent_id for r in responses]
        content_map = {r.agent_id: r.content for r in responses}
        n_prefs = len(rich)

        # Build pairwise win counts: wins[a][b] = # prefs where a is ranked above b.
        wins: dict[str, dict[str, int]] = {a: {b: 0 for b in agent_ids} for a in agent_ids}
        for pref in rich:
            for i, a in enumerate(pref.ordered_ids):
                for b in pref.ordered_ids[i + 1 :]:
                    if a in wins and b in wins:
                        wins[a][b] += 1

        others = {a: [b for b in agent_ids if b != a] for a in agent_ids}

        # Check for Condorcet winner: beats all others in strict majority.
        for candidate in agent_ids:
            rivals = others[candidate]
            if rivals and all(wins[candidate][b] > n_prefs / 2 for b in rivals):
                confidence = min(wins[candidate][b] / n_prefs for b in rivals)
                return AggregationResult(
                    final_answer=content_map.get(candidate, ""),
                    confidence=confidence,
                    method="Condorcet",
                )

        # Copeland fallback: score = wins - losses across pairwise contests.
        copeland: dict[str, float] = {a: 0.0 for a in agent_ids}
        for a in agent_ids:
            for b in others[a]:
                if wins[a][b] > wins[b][a]:
                    copeland[a] += 1.0
                elif wins[a][b] < wins[b][a]:
                    copeland[a] -= 1.0

        winner = max(copeland, key=lambda k: copeland[k])
        max_wins = len(agent_ids) - 1
        confidence = (copeland[winner] + max_wins) / (2 * max_wins) if max_wins > 0 else 1.0

        return AggregationResult(
            final_answer=content_map.get(winner, ""),
            confidence=max(0.0, min(1.0, confidence)),
            method="Copeland",
        )
