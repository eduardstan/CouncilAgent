"""TaskProfile — per-task configuration data object.

A TaskProfile bundles the normalizer, optional output schema, and aggregation
recommendation for a class of tasks. It is configuration data, not a pipeline
layer — it may import from council.normalizer to supply concrete defaults.

Constitution §2: TaskProfile is consumed by CouncilPolicy (Phase 3) to
produce a CouncilConfig, keeping the agent interface task-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from council.context import AnswerNormalizer


@dataclass(frozen=True, slots=True)
class TaskProfile:
    """Immutable task configuration passed from policy to pipeline components.

    Fields:
        name: Short human-readable label (e.g. "factual", "math").
        normalizer: AnswerNormalizer used for MajorityVote and AgreementThreshold.
        output_schema: Optional JSON schema injected into Protocol prompts.
        recommended_aggregation: Hint for CouncilPolicy — "majority_vote" or "meta_judge".
    """

    name: str
    normalizer: AnswerNormalizer
    output_schema: dict[str, object] | None = None
    recommended_aggregation: str = "majority_vote"

    # ------------------------------------------------------------------
    # Preset classmethods — deferred imports keep module loading fast
    # ------------------------------------------------------------------

    @classmethod
    def factual(cls) -> TaskProfile:
        """Short-answer factual questions with a single correct answer."""
        from council.normalizer import StructuredOutputNormalizer

        return cls(
            name="factual",
            normalizer=StructuredOutputNormalizer(),
            recommended_aggregation="majority_vote",
        )

    @classmethod
    def math(cls) -> TaskProfile:
        """Numerical or symbolic math problems."""
        from council.normalizer import StructuredOutputNormalizer

        return cls(
            name="math",
            normalizer=StructuredOutputNormalizer(),
            recommended_aggregation="majority_vote",
        )

    @classmethod
    def open_ended(cls) -> TaskProfile:
        """Open-ended questions where agreement is rare; use LLM synthesis."""
        from council.normalizer import IdentityNormalizer

        return cls(
            name="open_ended",
            normalizer=IdentityNormalizer(),
            recommended_aggregation="meta_judge",
        )

    @classmethod
    def code(cls) -> TaskProfile:
        """Code generation tasks; identity normalizer, LLM synthesis."""
        from council.normalizer import IdentityNormalizer

        return cls(
            name="code",
            normalizer=IdentityNormalizer(),
            recommended_aggregation="meta_judge",
        )
