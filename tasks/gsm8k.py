"""GSM8K task loader — grade-school math word problems.

Uses the Hugging Face `datasets` library to stream from the canonical
openai/gsm8k split. The ground-truth answer is the final numeric value
after the "####" delimiter in GSM8K's answer field.

fast mode:  loader.load(limit=10)   # 10 problems, ~seconds
full mode:  loader.load()           # full test split, ~1319 problems
"""

from __future__ import annotations

import re

from tasks.loader import BenchmarkTask, TaskLoader

_ANSWER_RE = re.compile(r"####\s*(.+)$", re.MULTILINE)


def _extract_answer(raw_answer: str) -> str:
    m = _ANSWER_RE.search(raw_answer)
    if m:
        return m.group(1).strip().replace(",", "")
    return raw_answer.strip()


class GSM8KLoader(TaskLoader):
    """Load problems from the GSM8K test split."""

    def __init__(self, split: str = "test") -> None:
        self._split = split

    @property
    def name(self) -> str:
        return "gsm8k"

    def load(self, limit: int | None = None) -> list[BenchmarkTask]:
        try:
            from datasets import load_dataset  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "GSM8KLoader requires the 'datasets' package. "
                "Install it with: uv pip install 'council-agent[benchmark]'"
            ) from e

        ds = load_dataset("openai/gsm8k", "main", split=self._split, trust_remote_code=False)
        tasks: list[BenchmarkTask] = []
        for i, row in enumerate(ds):
            if limit is not None and i >= limit:
                break
            tasks.append(
                BenchmarkTask(
                    id=f"gsm8k-{self._split}-{i}",
                    question=row["question"],
                    ground_truth=_extract_answer(row["answer"]),
                    domain="math",
                    difficulty=None,
                )
            )
        return tasks
