"""Tests for council/task_profile.py"""

from __future__ import annotations

import pytest

from council.normalizer import IdentityNormalizer, StructuredOutputNormalizer
from council.task_profile import TaskProfile


class TestTaskProfileDefaults:
    def test_custom_profile_stores_fields(self) -> None:
        normalizer = IdentityNormalizer()
        profile = TaskProfile(name="custom", normalizer=normalizer)
        assert profile.name == "custom"
        assert profile.normalizer is normalizer
        assert profile.output_schema is None
        assert profile.recommended_aggregation == "majority_vote"

    def test_with_output_schema(self) -> None:
        schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
        normalizer = IdentityNormalizer()
        profile = TaskProfile(name="structured", normalizer=normalizer, output_schema=schema)
        assert profile.output_schema == schema

    def test_is_frozen(self) -> None:
        normalizer = IdentityNormalizer()
        profile = TaskProfile(name="x", normalizer=normalizer)
        with pytest.raises((AttributeError, TypeError)):
            profile.name = "y"  # type: ignore[misc]


class TestTaskProfilePresets:
    """Verify that canonical preset configurations can be constructed correctly.

    Presets are caller-constructed; TaskProfile is a pure data container.
    These tests pin the expected shape of each preset so CouncilPolicy (Phase 3)
    can rely on the same conventions.
    """

    def test_factual_preset(self) -> None:
        profile = TaskProfile(
            name="factual",
            normalizer=StructuredOutputNormalizer(),
            recommended_aggregation="majority_vote",
        )
        assert profile.name == "factual"
        assert isinstance(profile.normalizer, StructuredOutputNormalizer)
        assert profile.recommended_aggregation == "majority_vote"

    def test_math_preset(self) -> None:
        profile = TaskProfile(
            name="math",
            normalizer=StructuredOutputNormalizer(),
            recommended_aggregation="majority_vote",
        )
        assert profile.name == "math"
        assert isinstance(profile.normalizer, StructuredOutputNormalizer)

    def test_open_ended_preset(self) -> None:
        profile = TaskProfile(
            name="open_ended",
            normalizer=IdentityNormalizer(),
            recommended_aggregation="meta_judge",
        )
        assert profile.name == "open_ended"
        assert isinstance(profile.normalizer, IdentityNormalizer)
        assert profile.recommended_aggregation == "meta_judge"

    def test_code_preset(self) -> None:
        profile = TaskProfile(
            name="code",
            normalizer=IdentityNormalizer(),
            recommended_aggregation="meta_judge",
        )
        assert profile.name == "code"
        assert isinstance(profile.normalizer, IdentityNormalizer)
        assert profile.recommended_aggregation == "meta_judge"

    def test_two_factual_profiles_are_distinct_instances(self) -> None:
        a = TaskProfile(name="factual", normalizer=StructuredOutputNormalizer())
        b = TaskProfile(name="factual", normalizer=StructuredOutputNormalizer())
        assert a is not b
        assert type(a.normalizer) is type(b.normalizer)
