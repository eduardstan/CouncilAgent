"""Tests for council/task_profile.py"""

from __future__ import annotations

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
        import pytest

        normalizer = IdentityNormalizer()
        profile = TaskProfile(name="x", normalizer=normalizer)
        with pytest.raises((AttributeError, TypeError)):
            profile.name = "y"  # type: ignore[misc]


class TestTaskProfilePresets:
    def test_factual_uses_structured_normalizer(self) -> None:
        profile = TaskProfile.factual()
        assert profile.name == "factual"
        assert isinstance(profile.normalizer, StructuredOutputNormalizer)
        assert profile.recommended_aggregation == "majority_vote"

    def test_math_uses_structured_normalizer(self) -> None:
        profile = TaskProfile.math()
        assert profile.name == "math"
        assert isinstance(profile.normalizer, StructuredOutputNormalizer)
        assert profile.recommended_aggregation == "majority_vote"

    def test_open_ended_uses_identity_normalizer(self) -> None:
        profile = TaskProfile.open_ended()
        assert profile.name == "open_ended"
        assert isinstance(profile.normalizer, IdentityNormalizer)
        assert profile.recommended_aggregation == "meta_judge"

    def test_code_uses_identity_normalizer(self) -> None:
        profile = TaskProfile.code()
        assert profile.name == "code"
        assert isinstance(profile.normalizer, IdentityNormalizer)
        assert profile.recommended_aggregation == "meta_judge"

    def test_presets_return_distinct_instances(self) -> None:
        a = TaskProfile.factual()
        b = TaskProfile.factual()
        # Each call returns a new instance (normalizers don't share identity)
        assert a is not b
        assert type(a.normalizer) is type(b.normalizer)
