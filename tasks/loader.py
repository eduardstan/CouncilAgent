"""Task loader contract and BenchmarkTask dataclass.

All task loaders implement TaskLoader. New datasets register themselves in
tasks/registry.py — no loader imports another loader.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BenchmarkTask:
    """Single evaluation instance.

    id:           Unique within a dataset (e.g. "gsm8k-train-42").
    question:     The prompt to send to the council.
    ground_truth: Canonical answer string (already in canonical form).
    domain:       Dataset family (e.g. "math", "factual", "coding").
    difficulty:   Optional coarse difficulty label (easy / medium / hard).
    """

    id: str
    question: str
    ground_truth: str
    domain: str
    difficulty: str | None = None


class TaskLoader(ABC):
    """Load BenchmarkTask instances from a dataset."""

    @abstractmethod
    def load(self, limit: int | None = None) -> list[BenchmarkTask]:
        """Return up to `limit` tasks (all tasks if limit is None)."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Dataset identifier used in registry and MLflow logging."""
        ...
