"""Evaluation metrics for CouncilAgent benchmark runs.

All functions are pure (no I/O, no model calls). The Embedder protocol is
injected for diversity_trajectory — sentence-transformers in full mode.

Approved import: evaluation/ may import council/ (downstream, not a peer layer).
See architecture.md "Approved exception: evaluation → council".
"""

from __future__ import annotations

import re
from typing import Protocol

from council.context import AnswerNormalizer, CouncilState
from council.normalizer import IdentityNormalizer


# ---------------------------------------------------------------------------
# Embedder protocol (injected for diversity_trajectory)
# ---------------------------------------------------------------------------


class Embedder(Protocol):
    """Encode a list of texts into dense vectors."""

    def encode(self, texts: list[str]) -> list[list[float]]: ...


# ---------------------------------------------------------------------------
# task_accuracy  (Issue 9 regression fix — word-boundary match)
# ---------------------------------------------------------------------------

_NUMERIC_RE = re.compile(r"\b\d+(?:[.,]\d+)*\b")


def _word_boundary_match(prediction: str, ground_truth: str) -> bool:
    """Return True if ground_truth appears as a whole token in prediction.

    Issue 9 ground truth: "The answer is 172." vs ground_truth "72" must return
    False — "72" is not a whole token within "172".
    """
    # Escape special regex chars in ground_truth then require word boundaries.
    pattern = r"(?<![0-9a-zA-Z])" + re.escape(ground_truth) + r"(?![0-9a-zA-Z])"
    return bool(re.search(pattern, prediction))


async def task_accuracy(
    prediction: str,
    ground_truth: str,
    method: str = "smart",
    normalizer: AnswerNormalizer | None = None,
) -> float:
    """Return 1.0 if prediction matches ground_truth, else 0.0.

    method="smart":
        1. Normalise both strings via `normalizer` (defaults to IdentityNormalizer).
        2. Exact-match on normalised forms.
        3. If that fails, use word-boundary matching on the original strings.
    method="exact":
        Case-insensitive exact match after stripping whitespace.

    Async because AnswerNormalizer.normalize is async (consistent with the
    async-first codebase; experiment runners await this call).
    """
    if method == "exact":
        return 1.0 if prediction.strip().lower() == ground_truth.strip().lower() else 0.0

    # smart: normalise → exact, then word-boundary fallback
    _normalizer = normalizer if normalizer is not None else IdentityNormalizer()
    norm_pred = await _normalizer.normalize(prediction)
    norm_gt = await _normalizer.normalize(ground_truth)

    if norm_pred == norm_gt:
        return 1.0
    return 1.0 if _word_boundary_match(prediction, ground_truth) else 0.0


# ---------------------------------------------------------------------------
# convergence_rate
# ---------------------------------------------------------------------------


def convergence_rate(agreement_per_round: list[float]) -> float:
    """Area under the agreement curve, normalised to [0, 1].

    Measures how quickly agreement rises across rounds. A council that reaches
    full agreement in round 1 scores higher than one that converges gradually.
    Trapezoidal AUC normalised by the maximum possible area (n_rounds * 1.0).

    Returns 0.0 for empty or single-element lists (no curve to integrate).
    """
    n = len(agreement_per_round)
    if n < 2:
        return float(agreement_per_round[0]) if n == 1 else 0.0

    auc = sum(
        (agreement_per_round[i] + agreement_per_round[i + 1]) / 2.0
        for i in range(n - 1)
    )
    max_area = float(n - 1)
    return auc / max_area if max_area > 0 else 0.0


# ---------------------------------------------------------------------------
# deliberation_efficiency
# ---------------------------------------------------------------------------


def deliberation_efficiency(accuracy_delta: float, tokens_spent: int) -> float:
    """Accuracy gain per 1 000 tokens spent on deliberation.

    accuracy_delta: final_accuracy - baseline_accuracy (can be negative).
    tokens_spent:   total tokens consumed in deliberation rounds (> 0).
    Returns 0.0 if tokens_spent == 0 (degenerate: no deliberation happened).
    """
    if tokens_spent <= 0:
        return 0.0
    return accuracy_delta / (tokens_spent / 1_000.0)


# ---------------------------------------------------------------------------
# communication_cost
# ---------------------------------------------------------------------------


def communication_cost(state: CouncilState) -> dict[str, int | float]:
    """Summarise token and API-call costs from a completed council run.

    Reads CouncilState.round_history — a list of AgentResponse objects —
    and returns a dict with keys: total_tokens_in, total_tokens_out,
    total_tokens, api_calls, rounds_used.
    """
    tokens_in = sum(r.tokens_in for r in state.round_history)
    tokens_out = sum(r.tokens_out for r in state.round_history)
    api_calls = len(state.round_history)
    rounds_used = (
        max((r.round_index for r in state.round_history), default=-1) + 1
        if state.round_history
        else 0
    )
    return {
        "total_tokens_in": tokens_in,
        "total_tokens_out": tokens_out,
        "total_tokens": tokens_in + tokens_out,
        "api_calls": api_calls,
        "rounds_used": rounds_used,
    }


# ---------------------------------------------------------------------------
# inter_rater_agreement  (Cohen's κ, pair-averaged)
# ---------------------------------------------------------------------------


def inter_rater_agreement(rankings: list[list[str]]) -> float:
    """Pair-averaged Cohen's κ across a set of rater rankings.

    Each element of `rankings` is an ordered list of candidate IDs from one
    rater. Converts each ranking to pairwise preference labels and computes
    Cohen's κ for each pair of raters, then averages.

    Returns 1.0 for perfect agreement, ~0.0 for chance-level agreement,
    and can be negative for systematic disagreement.
    Returns 0.0 for fewer than 2 raters or 0-/1-candidate rankings.
    """
    if len(rankings) < 2:
        return 0.0

    def _pairwise_labels(ranking: list[str]) -> dict[tuple[str, str], int]:
        labels: dict[tuple[str, str], int] = {}
        for i, a in enumerate(ranking):
            for b in ranking[i + 1 :]:
                labels[(a, b)] = 1  # a preferred over b
                labels[(b, a)] = 0
        return labels

    def _cohens_kappa(labels_a: dict[tuple[str, str], int], labels_b: dict[tuple[str, str], int]) -> float:
        common = set(labels_a) & set(labels_b)
        if not common:
            return 0.0
        n = len(common)
        agree = sum(1 for k in common if labels_a[k] == labels_b[k])
        p_o = agree / n
        # Marginal frequencies for expected agreement
        p_a1 = sum(labels_a[k] for k in common) / n
        p_b1 = sum(labels_b[k] for k in common) / n
        p_e = p_a1 * p_b1 + (1 - p_a1) * (1 - p_b1)
        if p_e == 1.0:
            return 1.0 if p_o == 1.0 else 0.0
        return (p_o - p_e) / (1.0 - p_e)

    pairwise = [_pairwise_labels(r) for r in rankings]
    kappas: list[float] = []
    for i in range(len(pairwise)):
        for j in range(i + 1, len(pairwise)):
            kappas.append(_cohens_kappa(pairwise[i], pairwise[j]))

    return sum(kappas) / len(kappas) if kappas else 0.0


# ---------------------------------------------------------------------------
# diversity_trajectory
# ---------------------------------------------------------------------------


def diversity_trajectory(
    responses_per_round: list[list[str]],
    embedder: Embedder | None = None,
) -> list[float]:
    """Diversity score per round using sentence embeddings (cosine distance).

    With an embedder: average pairwise cosine distance among response vectors.
    Without an embedder: raises ValueError — embedder is required (Decision 4).

    Returns a list of floats in [0, 1], one per round.
    Returns [0.0] * n_rounds for rounds with ≤1 response.
    """
    if embedder is None:
        raise ValueError(
            "diversity_trajectory requires an Embedder. "
            "Pass a SentenceTransformerEmbedder instance (see evaluation/metrics.py)."
        )

    scores: list[float] = []
    for round_responses in responses_per_round:
        if len(round_responses) <= 1:
            scores.append(0.0)
            continue
        vecs = embedder.encode(round_responses)
        scores.append(_mean_pairwise_cosine_distance(vecs))
    return scores


def _mean_pairwise_cosine_distance(vecs: list[list[float]]) -> float:
    """Average pairwise cosine distance (1 - cosine_similarity) among vectors."""
    import math

    n = len(vecs)
    total = 0.0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            dot = sum(a * b for a, b in zip(vecs[i], vecs[j]))
            norm_i = math.sqrt(sum(a * a for a in vecs[i]))
            norm_j = math.sqrt(sum(a * a for a in vecs[j]))
            if norm_i > 0 and norm_j > 0:
                sim = dot / (norm_i * norm_j)
                total += 1.0 - sim
            count += 1
    return total / count if count > 0 else 0.0


# ---------------------------------------------------------------------------
# SentenceTransformerEmbedder — concrete Embedder for full mode
# ---------------------------------------------------------------------------


class SentenceTransformerEmbedder:
    """Embedder backed by sentence-transformers.

    Requires: uv pip install 'council-agent[benchmark]'
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "SentenceTransformerEmbedder requires sentence-transformers. "
                "Install with: uv pip install 'council-agent[benchmark]'"
            ) from e
        self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(texts, convert_to_numpy=True)
        return [v.tolist() for v in vecs]
