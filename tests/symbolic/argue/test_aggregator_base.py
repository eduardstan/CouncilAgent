"""Tests for council/symbolic/argue/aggregator_base.py — Aggregator ABC.

The ABC is the single L2 contract. The signature is:

    async def aggregate(self, trace: Trace, *, original_question: str)
        -> AggregationResult

Notably:
  - `original_question` is keyword-only — no positional-arg confusion.
  - `trace` is the only positional argument — there is no `responses` overload
    (D8 fix from the deep review at the type level: aggregator inputs are
    typed Traces, never raw response lists).
  - `aggregate` is async — the future calibrator hook in PR2 may need to await
    a per-domain calibrator that itself awaits a privileged-knowledge fetch.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from council.context import BAFMarginConfidence
from council.dialect.trace import Trace
from council.symbolic.argue.aggregation_result import AggregationResult
from council.symbolic.argue.aggregator_base import Aggregator


class _FixedAnswerAggregator(Aggregator):
    """Test-only concrete subclass — returns a constant answer."""

    async def aggregate(
        self, trace: Trace, *, original_question: str
    ) -> AggregationResult:
        return AggregationResult(
            answer="42",
            confidence=BAFMarginConfidence(value=0.5),
            method="FixedAnswerAggregator",
            metadata={"original_question": original_question},
        )


class _MissingMethodAggregator(Aggregator):
    """Subclass that does NOT override aggregate — should fail to instantiate."""


class TestAggregatorABC:
    def test_cannot_instantiate_abstract_base(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            Aggregator()  # type: ignore[abstract]

    def test_concrete_subclass_instantiates(self) -> None:
        agg = _FixedAnswerAggregator()
        assert isinstance(agg, Aggregator)

    def test_subclass_without_aggregate_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            _MissingMethodAggregator()  # type: ignore[abstract]


class TestAggregatorContract:
    def test_aggregate_is_coroutine_function(self) -> None:
        # `aggregate` must be `async def` — the @abstractmethod decorator
        # alone doesn't enforce this, so we check explicitly.
        assert inspect.iscoroutinefunction(Aggregator.aggregate)

    def test_aggregate_signature_keyword_only_original_question(self) -> None:
        sig = inspect.signature(Aggregator.aggregate)
        params = sig.parameters
        assert "trace" in params
        assert "original_question" in params
        assert params["trace"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert params["original_question"].kind == inspect.Parameter.KEYWORD_ONLY

    def test_aggregate_no_responses_overload(self) -> None:
        # D8 fix: trace is the only data input — no `responses` parameter.
        sig = inspect.signature(Aggregator.aggregate)
        assert "responses" not in sig.parameters
        assert "round_history" not in sig.parameters
        assert "original_prompt" not in sig.parameters

    def test_concrete_aggregate_returns_aggregation_result(self) -> None:
        agg = _FixedAnswerAggregator()
        result = asyncio.run(
            agg.aggregate(Trace(), original_question="What is 6 * 7?")
        )
        assert isinstance(result, AggregationResult)
        assert result.answer == "42"
        assert result.metadata["original_question"] == "What is 6 * 7?"

    def test_aggregate_rejects_positional_original_question(self) -> None:
        agg = _FixedAnswerAggregator()
        # Passing original_question positionally violates the kw-only rule.
        with pytest.raises(TypeError):
            asyncio.run(agg.aggregate(Trace(), "not allowed positionally"))  # type: ignore[misc]
