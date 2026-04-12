"""Baseline runners for CouncilAgent benchmark evaluation.

All baselines operate on pre-collected AgentResponse lists — they never call
models. This satisfies Constitution §1 (benchmarking doesn't execute councils)
and §7 (cost is always tracked, even if 0.0 for response-reuse baselines).

Approved import: evaluation/ may import council/ (see architecture.md).
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

from council.context import AgentResponse
from council.normalizer import AnswerNormalizer


@dataclass(frozen=True, slots=True)
class BaselineResult:
    """Result from a single baseline run.

    answer:   The baseline's chosen answer string.
    accuracy: 1.0 if correct, 0.0 if wrong, None if ground_truth unknown.
    cost:     Total cost in USD (0.0 for baselines that reuse pre-collected responses).
    """

    name: str
    answer: str
    accuracy: float | None
    cost: float


async def majority_vote_no_deliberation(
    responses: list[AgentResponse],
    normalizer: AnswerNormalizer,
    ground_truth: str | None = None,
) -> BaselineResult:
    """Plurality vote on normalised responses — no deliberation rounds.

    This is the §6 baseline: every council run must beat this. Uses the same
    normalizer as MajorityVote aggregation for a fair comparison.
    """
    if not responses:
        return BaselineResult(name="majority_vote_no_deliberation", answer="", accuracy=None, cost=0.0)

    pairs = [(await normalizer.normalize(r.content), r.content) for r in responses]
    counts: Counter[str] = Counter(canonical for canonical, _ in pairs)
    winner_canonical, _ = counts.most_common(1)[0]

    accuracy = _accuracy(winner_canonical, ground_truth, normalizer) if ground_truth is not None else None
    return BaselineResult(
        name="majority_vote_no_deliberation",
        answer=winner_canonical,
        accuracy=accuracy,
        cost=0.0,
    )


async def best_single_model(
    responses: list[AgentResponse],
    normalizer: AnswerNormalizer,
    ground_truth: str | None = None,
) -> BaselineResult:
    """Best possible answer from any single agent (oracle over agents).

    Selects the response whose normalised form matches ground_truth. If no
    response matches, returns the first response (arbitrary tie-break).
    ground_truth must be provided; returns accuracy=None otherwise.
    """
    if not responses:
        return BaselineResult(name="best_single_model", answer="", accuracy=None, cost=0.0)

    if ground_truth is not None:
        gt_norm = await normalizer.normalize(ground_truth)
        for r in responses:
            if await normalizer.normalize(r.content) == gt_norm:
                return BaselineResult(
                    name="best_single_model",
                    answer=r.content,
                    accuracy=1.0,
                    cost=r.cost,
                )

    first = responses[0]
    norm = await normalizer.normalize(first.content)
    accuracy = _accuracy(norm, ground_truth, normalizer) if ground_truth is not None else None
    return BaselineResult(name="best_single_model", answer=first.content, accuracy=accuracy, cost=first.cost)


async def self_consistency(
    responses: list[AgentResponse],
    normalizer: AnswerNormalizer,
    ground_truth: str | None = None,
) -> BaselineResult:
    """Self-consistency: same as majority_vote_no_deliberation (no chain-of-thought here).

    In the LLM-council setting, self-consistency is equivalent to plurality
    vote on the first-round responses. Named separately for clarity in results.
    """
    result = await majority_vote_no_deliberation(responses, normalizer, ground_truth)
    return BaselineResult(
        name="self_consistency",
        answer=result.answer,
        accuracy=result.accuracy,
        cost=result.cost,
    )


async def random_vote(
    responses: list[AgentResponse],
    normalizer: AnswerNormalizer,
    ground_truth: str | None = None,
    seed: int = 0,
) -> BaselineResult:
    """Pick a random response. Lower-bound baseline."""
    if not responses:
        return BaselineResult(name="random_vote", answer="", accuracy=None, cost=0.0)

    rng = random.Random(seed)
    chosen = rng.choice(responses)
    norm = await normalizer.normalize(chosen.content)
    accuracy = _accuracy(norm, ground_truth, normalizer) if ground_truth is not None else None
    return BaselineResult(name="random_vote", answer=norm, accuracy=accuracy, cost=0.0)


async def oracle_best_of_n(
    responses: list[AgentResponse],
    normalizer: AnswerNormalizer,
    ground_truth: str,
) -> BaselineResult:
    """Upper-bound oracle: returns 1.0 accuracy if any agent got it right.

    Models the theoretical ceiling — how well N agents could do if we knew
    which one was correct.
    """
    if not responses:
        return BaselineResult(name="oracle_best_of_n", answer="", accuracy=0.0, cost=0.0)

    gt_norm = await normalizer.normalize(ground_truth)
    for r in responses:
        if await normalizer.normalize(r.content) == gt_norm:
            return BaselineResult(name="oracle_best_of_n", answer=r.content, accuracy=1.0, cost=r.cost)

    first = responses[0]
    return BaselineResult(name="oracle_best_of_n", answer=first.content, accuracy=0.0, cost=first.cost)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _accuracy(
    normalised_prediction: str,
    ground_truth: str | None,
    normalizer: AnswerNormalizer,
) -> float | None:
    """Synchronous exact-match on already-normalised prediction vs ground_truth."""
    if ground_truth is None:
        return None
    # ground_truth normalisation happens at call sites (async) — here we just
    # compare the already-normalised prediction against a stripped/lowered gt.
    return 1.0 if normalised_prediction == ground_truth.strip().lower() else 0.0
