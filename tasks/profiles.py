"""Per-dataset TaskProfile presets.

A TaskProfile bundles everything a runner needs to shape prompts and
aggregation for a dataset: normalizer, output schema, recommended
aggregation, and a prompt hint that steers the model toward the expected
answer format.

This module is the single source of truth for dataset defaults. The
benchmark runner consults it via dataset name; experiment configs may
override any field. No file outside tasks/ and experiments/ imports
from here.
"""

from __future__ import annotations

from council.normalizer import StructuredOutputNormalizer
from council.task_profile import TaskProfile

_ANSWER_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string", "description": "Step-by-step working"},
        "answer": {
            "type": "string",
            "description": "Concise final answer only (e.g. a number or short phrase)",
        },
    },
    "required": ["reasoning", "answer"],
}

_GSM8K_HINT = (
    "For the 'answer' field: return ONLY the final numeric value with no "
    "units, words, currency symbols, or thousands separators. "
    "For example: '72', '18.50', '-3'. Not: '72 dollars', '$18.50', '1,234'."
)

PROFILES: dict[str, TaskProfile] = {
    "gsm8k": TaskProfile(
        name="gsm8k",
        normalizer=StructuredOutputNormalizer(),
        output_schema=_ANSWER_SCHEMA,
        recommended_aggregation="majority_vote",
        prompt_hint=_GSM8K_HINT,
    ),
}


def get_profile(dataset: str) -> TaskProfile:
    """Return the registered TaskProfile for a dataset, raising on unknown names."""
    if dataset not in PROFILES:
        raise ValueError(
            f"Unknown dataset {dataset!r}. Register a TaskProfile in tasks/profiles.py. "
            f"Known: {sorted(PROFILES)}"
        )
    return PROFILES[dataset]
