"""TaskProfile dataclass + per-dataset registry.

Surface overrides allow per-dataset answer-format instructions to be injected
into the prompt (architecture rule: Claim.domain controls format, tasks/ controls
dataset-specific overrides).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TaskProfile:
    name: str
    description: str
    answer_format: str  # "numeric" | "free" | "code" | "json"
    surface_overrides: dict[str, str] = field(default_factory=dict)


REGISTRY: dict[str, TaskProfile] = {
    "gsm8k": TaskProfile(
        name="gsm8k",
        description="Grade-school math word problems — GSM8K benchmark (Cobbe et al. 2021).",
        answer_format="numeric",
        surface_overrides={
            "answer_instruction": (
                "Solve step by step. At the end write 'The answer is <number>.' "
                "with a single integer."
            ),
        },
    ),
    "arc_agi": TaskProfile(
        name="arc_agi",
        description="ARC-AGI visual reasoning tasks — grid transformations.",
        answer_format="json",
    ),
    "mmlu": TaskProfile(
        name="mmlu",
        description="Massive Multitask Language Understanding — 57 subjects.",
        answer_format="free",
        surface_overrides={
            "answer_instruction": "Answer with only the letter (A, B, C, or D).",
        },
    ),
}
