"""Aggregation layer — reduce agent responses to a final answer.

Constitution §3: aggregation reduces only. It must not construct deliberation
prompts, mutate state history, or hardcode a synthesis model.
Constitution §9: one correct MajorityVote first. BordaCount and MetaJudge are
Phase 3 work — stubs raise NotImplementedError.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from collections.abc import Callable

from council.context import (
    AgentResponse,
    AggregationResult,
    AnswerNormalizer,
    PreferenceData,
    RichPreference,
)
from council.models import ModelClient, ModelFailure, ModelRequest

logger = logging.getLogger(__name__)


class Aggregation(ABC):
    """Reduce a list of agent responses (and optional preferences) to a single answer.

    The optional round_history parameter carries the full deliberation history.
    Blind aggregators (MajorityVote, BordaCount, Condorcet) ignore it.
    Informed aggregators (MetaJudge) use it to trace how consensus formed.
    See Issue 11 in LLMCouncil_Deep_Review.md for the design rationale.

    The optional original_prompt parameter carries the user's question. MetaJudge
    uses it to anchor the synthesis prompt so the judge answers the actual task
    rather than guessing it from the debate. Blind aggregators ignore it.
    """

    @abstractmethod
    async def aggregate(
        self,
        responses: list[AgentResponse],
        preferences: list[PreferenceData] | None = None,
        round_history: list[AgentResponse] | None = None,
        original_prompt: str | None = None,
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
        round_history: list[AgentResponse] | None = None,
        original_prompt: str | None = None,
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
        round_history: list[AgentResponse] | None = None,
        original_prompt: str | None = None,
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


def _default_round_label(round_index: int) -> str:
    """Label rounds by parity: even = ANSWER, odd = CRITIQUE.

    This is a heuristic for PeerReviewProtocol-style alternation. For other
    protocols, inject a custom round_label_fn at MetaJudge construction time.
    MetaJudge intentionally does NOT import Protocol (cross-layer violation).
    """
    return "ANSWER" if round_index % 2 == 0 else "CRITIQUE"


class MetaJudge(Aggregation):
    """LLM-based synthesis aggregation — the "informed Area Chair" model.

    When round_history is provided to aggregate(), MetaJudge builds a structured
    debate transcript labelled by phase (GENERATE/CRITIQUE/REVISION) so the
    synthesis model can trace how consensus formed. Without round_history it falls
    back to a flat list of the final-round responses.

    The synthesis model and ModelClient are injected at construction — never
    hardcoded (Constitution §3). MetaJudge does NOT import Protocol; round labels
    come from round_index alone via the injected round_label_fn.

    Confidence (Constitution §5): when a normalizer is injected, confidence is
    the fraction of final-round agent responses whose canonical form matches
    the synthesized answer's canonical form. Without a normalizer, confidence
    falls back to 1.0 (sentinel — the synthesis model spoke, no calibration).
    """

    def __init__(
        self,
        model: str,
        model_client: ModelClient,
        round_label_fn: Callable[[int], str] | None = None,
        response_format: dict[str, object] | None = None,
        normalizer: AnswerNormalizer | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> None:
        self._model = model
        self._model_client = model_client
        self._round_label_fn = round_label_fn or _default_round_label
        self._response_format = response_format
        self._normalizer = normalizer
        self._temperature = temperature
        self._max_tokens = max_tokens

    def _format_debate(self, round_history: list[AgentResponse]) -> str:
        """Format the full deliberation history as a phase-labelled transcript.

        Agent labels are stable across rounds: the same agent_id is always
        rendered as the same "Response X" marker, derived from a sort over
        the union of agent_ids seen in the history. This lets the synthesis
        model track how each participant's position evolved — critical for
        the "informed Area Chair" reading of the debate.
        """
        by_round: dict[int, list[AgentResponse]] = defaultdict(list)
        for r in round_history:
            by_round[r.round_index].append(r)

        # Stable label mapping: sorted agent_ids → A, B, C, …
        all_agent_ids = sorted({r.agent_id for r in round_history})
        label_map = {aid: chr(65 + i) for i, aid in enumerate(all_agent_ids)}

        sections: list[str] = []
        for round_idx in sorted(by_round):
            label = self._round_label_fn(round_idx)
            phase_label = "GENERATE" if round_idx == 0 else label
            sections.append(f"### Round {round_idx} — {phase_label}")
            for r in sorted(by_round[round_idx], key=lambda x: x.agent_id):
                sections.append(f"[Response {label_map[r.agent_id]}]:\n{r.content}")
        return "\n\n".join(sections)

    async def aggregate(
        self,
        responses: list[AgentResponse],
        preferences: list[PreferenceData] | None = None,
        round_history: list[AgentResponse] | None = None,
        original_prompt: str | None = None,
    ) -> AggregationResult:
        if not responses:
            return AggregationResult(final_answer="", confidence=0.0, method="MetaJudge")

        # Anchor the synthesis on the original question so the judge answers
        # the actual task rather than inferring it from the transcript.
        task_section = (
            f"## Original question\n{original_prompt}\n\n" if original_prompt else ""
        )

        if round_history:
            debate_section = self._format_debate(round_history)
            prompt = (
                "You are a synthesis judge reviewing a multi-round deliberation. "
                "Below is the full debate transcript, organized by round. "
                "Synthesize the best final answer, taking into account how the "
                "agents' positions evolved through critique and revision.\n\n"
                f"{task_section}"
                f"## Debate transcript\n{debate_section}\n\n"
                "Provide your synthesized final answer:"
            )
        else:
            # Fallback: flat list of final-round responses only.
            formatted = "\n\n".join(
                f"[Response {chr(65 + i)}]:\n{r.content}"
                for i, r in enumerate(responses)
            )
            prompt = (
                "You are a synthesis judge. Below are responses from multiple agents "
                "to a question. Synthesize them into a single best answer.\n\n"
                f"{task_section}"
                f"## Responses\n{formatted}\n\n"
                "Provide your synthesized answer:"
            )

        outcome = await self._model_client.call(
            ModelRequest(
                model=self._model,
                prompt=prompt,
                response_format=self._response_format,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            ),
        )
        if isinstance(outcome, ModelFailure):
            logger.warning("MetaJudge model call failed: %s", outcome.error)
            return AggregationResult(final_answer="", confidence=0.0, method="MetaJudge")

        confidence = 1.0
        if self._normalizer is not None:
            synth_canonical = await self._normalizer.normalize(outcome.content)
            matches = 0
            for r in responses:
                agent_canonical = await self._normalizer.normalize(r.content)
                if agent_canonical == synth_canonical:
                    matches += 1
            confidence = matches / len(responses) if responses else 0.0

        return AggregationResult(
            final_answer=outcome.content,
            confidence=confidence,
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
        round_history: list[AgentResponse] | None = None,
        original_prompt: str | None = None,
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
