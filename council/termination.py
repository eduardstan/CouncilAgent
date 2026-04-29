"""L0 — TerminationStrategy ABC + concrete strategies.

All strategies are pure functions over (Trace, round_index) — no model calls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from council.dialect.trace import Trace


class TerminationStrategy(ABC):
    """Decides whether a council run should stop."""

    @abstractmethod
    def should_stop(self, trace: Trace, round_index: int) -> tuple[bool, str]: ...


@dataclass(frozen=True, slots=True)
class FixedRounds(TerminationStrategy):
    """Stop after a fixed number of deliberation rounds."""

    max_rounds: int = 2

    def should_stop(self, trace: Trace, round_index: int) -> tuple[bool, str]:
        if round_index >= self.max_rounds:
            return (True, f"FixedRounds({self.max_rounds})")
        return (False, "")


class CompositeTermination(TerminationStrategy):
    """Stop as soon as any constituent strategy fires."""

    def __init__(self, strategies: list[TerminationStrategy]) -> None:
        self._strategies = strategies

    def should_stop(self, trace: Trace, round_index: int) -> tuple[bool, str]:
        for strategy in self._strategies:
            stop, reason = strategy.should_stop(trace, round_index)
            if stop:
                return (True, reason)
        return (False, "")
