"""Termination strategies — decide when the council pipeline should stop.

Constitution §3: termination reads CouncilState and returns (should_stop, reason).
It must NOT mutate state, call aggregation, or construct prompts.

Each strategy is checked after a round completes. The pipeline calls
should_stop() and exits the deliberation loop if it returns True.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import Counter

from council.context import AnswerNormalizer, CouncilState

logger = logging.getLogger(__name__)


class TerminationStrategy(ABC):
    """Decide whether the council should stop after the current round."""

    @abstractmethod
    async def should_stop(self, state: CouncilState) -> tuple[bool, str]:
        """Return (True, reason) to halt; (False, '') to continue."""
        ...


class FixedRounds(TerminationStrategy):
    """Stop after exactly max_rounds rounds have completed."""

    def __init__(self, max_rounds: int) -> None:
        if max_rounds < 1:
            raise ValueError(f"max_rounds must be >= 1, got {max_rounds}")
        self._max_rounds = max_rounds

    async def should_stop(self, state: CouncilState) -> tuple[bool, str]:
        if state.current_round >= self._max_rounds:
            return True, f"max_rounds={self._max_rounds}"
        return False, ""


class AgreementThreshold(TerminationStrategy):
    """Stop when the fraction of last-round responses sharing a canonical answer >= threshold.

    The normalizer is required (Option A from architecture review) so this module
    stays free of peer-layer imports (Constitution §3).
    """

    def __init__(self, threshold: float, normalizer: AnswerNormalizer) -> None:
        if not (0.0 < threshold <= 1.0):
            raise ValueError(f"threshold must be in (0, 1], got {threshold}")
        self._threshold = threshold
        self._normalizer = normalizer

    async def should_stop(self, state: CouncilState) -> tuple[bool, str]:
        last_round = state.current_round - 1
        last_responses = [r for r in state.round_history if r.round_index == last_round]
        if not last_responses:
            return False, ""

        canonicals = [await self._normalizer.normalize(r.content) for r in last_responses]
        counts: Counter[str] = Counter(canonicals)
        _top, top_count = counts.most_common(1)[0]
        agreement = top_count / len(canonicals)

        if agreement >= self._threshold:
            return True, f"agreement {agreement:.0%} >= {self._threshold:.0%}"
        return False, ""


class BudgetExhaustion(TerminationStrategy):
    """Stop when the accumulated cost reaches or exceeds budget_usd."""

    def __init__(self, budget_usd: float) -> None:
        if budget_usd <= 0.0:
            raise ValueError(f"budget_usd must be > 0, got {budget_usd}")
        self._budget = budget_usd

    async def should_stop(self, state: CouncilState) -> tuple[bool, str]:
        if state.total_cost >= self._budget:
            return True, f"budget_exhausted (${state.total_cost:.4f} >= ${self._budget:.4f})"
        return False, ""


class CompositeTermination(TerminationStrategy):
    """Stop when ANY sub-strategy returns True (logical OR).

    Strategies are evaluated in order; the first to return True wins.
    """

    def __init__(self, *strategies: TerminationStrategy) -> None:
        if not strategies:
            raise ValueError("CompositeTermination requires at least one strategy")
        self._strategies = strategies

    async def should_stop(self, state: CouncilState) -> tuple[bool, str]:
        for strategy in self._strategies:
            stop, reason = await strategy.should_stop(state)
            if stop:
                return True, reason
        return False, ""
