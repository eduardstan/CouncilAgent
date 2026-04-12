"""TaskProfile — per-task configuration data object.

A TaskProfile bundles the normalizer, optional output schema, and aggregation
recommendation for a class of tasks.

Constitution §2: TaskProfile is consumed by CouncilPolicy (Phase 3) to
produce a CouncilConfig, keeping the agent interface task-agnostic.
Constitution §3: this module imports only from council.context — callers
are responsible for injecting a concrete AnswerNormalizer.
"""

from __future__ import annotations

from dataclasses import dataclass

from council.context import AnswerNormalizer


@dataclass(frozen=True, slots=True)
class TaskProfile:
    """Immutable task configuration passed from policy to pipeline components.

    Fields:
        name: Short human-readable label (e.g. "factual", "math").
        normalizer: AnswerNormalizer used for MajorityVote and AgreementThreshold.
        output_schema: Optional JSON schema injected into Protocol prompts.
        recommended_aggregation: Hint for CouncilPolicy — "majority_vote" or "meta_judge".

    Preset convenience instances are created by callers (e.g. CouncilPolicy in Phase 3)
    that already import from council.normalizer. TaskProfile itself stays layer-clean.
    """

    name: str
    normalizer: AnswerNormalizer
    output_schema: dict[str, object] | None = None
    recommended_aggregation: str = "majority_vote"
