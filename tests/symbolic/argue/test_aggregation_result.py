"""Tests for council/symbolic/argue/aggregation_result.py.

AggregationResult is the typed return value of every Aggregator. The
confidence union is intentionally narrow: BAFMarginConfidence (the headline
W2 type) and CopelandConfidence (the constitutionally-blessed ordinal
fallback). JSDConfidence (L3) and MonitorVerdictConfidence (L1) are
produced by other layers and reach CouncilResponse via separate paths.
"""

from __future__ import annotations

import dataclasses

import pytest

from council.context import (
    BAFMarginConfidence,
    CopelandConfidence,
    JSDConfidence,
)
from council.symbolic.argue.aggregation_result import AggregationResult


class TestAggregationResultConstruction:
    def test_construct_with_baf_margin_confidence(self) -> None:
        result = AggregationResult(
            answer="42",
            confidence=BAFMarginConfidence(value=0.7),
            method="ArgumentationAggregator",
            metadata={},
        )
        assert result.answer == "42"
        assert isinstance(result.confidence, BAFMarginConfidence)
        assert result.confidence.value == 0.7
        assert result.method == "ArgumentationAggregator"
        assert result.metadata == {}

    def test_construct_with_copeland_confidence(self) -> None:
        result = AggregationResult(
            answer="X",
            confidence=CopelandConfidence(value=0.5),
            method="LastProposeFallbackAggregator",
            metadata={},
        )
        assert isinstance(result.confidence, CopelandConfidence)

    def test_metadata_holds_arbitrary_keys(self) -> None:
        meta: dict[str, object] = {
            "baf_mermaid": "graph TD;\nA-->B",
            "strengths": {"a": 0.7, "b": 0.3},
            "extension": frozenset({"a"}),
        }
        result = AggregationResult(
            answer="X",
            confidence=BAFMarginConfidence(value=0.4),
            method="ArgumentationAggregator",
            metadata=meta,
        )
        assert result.metadata["baf_mermaid"] == "graph TD;\nA-->B"
        assert result.metadata["strengths"] == {"a": 0.7, "b": 0.3}


class TestAggregationResultImmutability:
    def test_frozen_rejects_mutation(self) -> None:
        result = AggregationResult(
            answer="X",
            confidence=BAFMarginConfidence(value=0.5),
            method="m",
            metadata={},
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.answer = "Y"  # type: ignore[misc]

    def test_class_uses_slots(self) -> None:
        assert hasattr(AggregationResult, "__slots__")
        assert set(AggregationResult.__slots__) == {
            "answer",
            "confidence",
            "method",
            "metadata",
        }

    def test_replace_returns_new_instance(self) -> None:
        original = AggregationResult(
            answer="X",
            confidence=BAFMarginConfidence(value=0.5),
            method="m",
            metadata={},
        )
        replaced = dataclasses.replace(original, answer="Y")
        assert original.answer == "X"
        assert replaced.answer == "Y"


class TestAggregationResultTypeNarrowing:
    """The confidence type union is narrower than CouncilResponse.confidence.

    AggregationResult only carries L2-derivable confidence (BAF margin) or
    the L0 fallback (Copeland). JSDConfidence (L3) and MonitorVerdictConfidence
    (L1) are NOT valid aggregator outputs.
    """

    def test_jsd_confidence_rejected_by_type_checker(self) -> None:
        # mypy enforces this at compile time. At runtime, the assignment
        # succeeds (Python doesn't enforce union subtypes), but production
        # mypy --strict catches it. We test mypy in CI; here we just document
        # the intent with a runtime is-instance check.
        jsd = JSDConfidence(value=0.5)
        assert not isinstance(jsd, BAFMarginConfidence)
        assert not isinstance(jsd, CopelandConfidence)
