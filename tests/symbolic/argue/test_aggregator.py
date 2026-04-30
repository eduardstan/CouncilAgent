"""Tests for council/symbolic/argue/aggregator.py.

W2/PR6/Slice B ships two concrete Aggregators:

  - LastProposeFallbackAggregator: returns the last Propose's claim as the
    answer, with CopelandConfidence (Constitution §5 ordinal fallback).
    Used as the default fallback inside ArgumentationAggregator and as
    the W0/W1 baseline aggregator in CouncilContext.

  - ArgumentationAggregator: builds the QBAF, applies semantics
    (with prepare(trace) per ADR-0013), picks the strongest Propose-derived
    Argument as winner, computes BAFMarginConfidence as the
    (winner_strength - runner_up_strength) clamped to [0, 1].
    Carries the QBAF + strengths + extension in metadata.
"""

from __future__ import annotations

import asyncio

import pytest

from council.context import BAFMarginConfidence, CopelandConfidence
from council.dialect.moves import Claim, ClaimDomain, Concede, Propose, Vote
from council.dialect.trace import Trace
from council.symbolic.argue.aggregation_result import AggregationResult
from council.symbolic.argue.aggregator import (
    ArgumentationAggregator,
    LastProposeFallbackAggregator,
)
from council.symbolic.argue.baf import QBAF
from council.symbolic.argue.semantics.coupled import StrategicCoupledSemantics
from council.symbolic.argue.semantics.df_quad import DFQuADSemantics


def _propose(
    move_id: str,
    *,
    surface: str = "X",
    agent_id: str = "A",
    confidence: float = 0.5,
    evidence: tuple[str, ...] = (),
) -> Propose:
    return Propose(
        move_id=move_id,
        agent_id=agent_id,
        round_index=0,
        claim=Claim(surface=surface, domain=ClaimDomain.FREE, evidence=evidence),
        confidence=confidence,
    )


def _vote(
    move_id: str,
    *,
    surface: str = "X",
    agent_id: str = "A",
    confidence: float = 0.5,
    evidence: tuple[str, ...] = (),
) -> Vote:
    return Vote(
        move_id=move_id,
        agent_id=agent_id,
        round_index=1,
        option=Claim(surface=surface, evidence=evidence),
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# LastProposeFallbackAggregator
# ---------------------------------------------------------------------------


class TestLastProposeFallback:
    def test_empty_trace_returns_empty_answer(self) -> None:
        agg = LastProposeFallbackAggregator()
        result = asyncio.run(agg.aggregate(Trace(), original_question="Q?"))
        assert result.answer == ""
        assert isinstance(result.confidence, CopelandConfidence)
        assert result.method == "LastProposeFallbackAggregator"

    def test_returns_last_propose_claim_surface(self) -> None:
        agg = LastProposeFallbackAggregator()
        trace = (
            Trace()
            .append(_propose("p1", surface="X"))
            .append(_propose("p2", surface="Y"))
            .append(_propose("p3", surface="Z"))
        )
        result = asyncio.run(agg.aggregate(trace, original_question="Q?"))
        assert result.answer == "Z"

    def test_returns_copeland_confidence(self) -> None:
        agg = LastProposeFallbackAggregator()
        trace = Trace().append(_propose("p1"))
        result = asyncio.run(agg.aggregate(trace, original_question="Q?"))
        assert isinstance(result.confidence, CopelandConfidence)
        # ordinal fallback returns 0.5 — the constitutionally-blessed
        # neutral value (no plurality fraction, no faux precision)
        assert result.confidence.value == 0.5

    def test_method_name_in_result(self) -> None:
        agg = LastProposeFallbackAggregator()
        trace = Trace().append(_propose("p1", surface="X"))
        result = asyncio.run(agg.aggregate(trace, original_question="Q?"))
        assert result.method == "LastProposeFallbackAggregator"

    def test_metadata_includes_original_question(self) -> None:
        agg = LastProposeFallbackAggregator()
        trace = Trace().append(_propose("p1", surface="X"))
        result = asyncio.run(
            agg.aggregate(trace, original_question="What is X?")
        )
        # metadata should preserve the question for downstream (logging / demo)
        assert "original_question" in result.metadata
        assert result.metadata["original_question"] == "What is X?"


# ---------------------------------------------------------------------------
# ArgumentationAggregator — happy path
# ---------------------------------------------------------------------------


class TestArgumentationAggregatorHappyPath:
    """Multi-Propose trace; DF-QuAD strengths pick a winner with BAFMarginConfidence."""

    def test_picks_highest_strength_propose_as_answer(self) -> None:
        # Two Proposes with different base scores, no edges. DF-QuAD returns
        # base scores; winner is the higher-base Propose.
        agg = ArgumentationAggregator(semantics=DFQuADSemantics())
        trace = (
            Trace()
            .append(_propose("p1", surface="A", confidence=0.4))
            .append(_propose("p2", surface="B", confidence=0.7))
        )
        result = asyncio.run(agg.aggregate(trace, original_question="Q?"))
        assert result.answer == "B"

    def test_returns_baf_margin_confidence(self) -> None:
        agg = ArgumentationAggregator(semantics=DFQuADSemantics())
        trace = (
            Trace()
            .append(_propose("p1", surface="A", confidence=0.4))
            .append(_propose("p2", surface="B", confidence=0.7))
        )
        result = asyncio.run(agg.aggregate(trace, original_question="Q?"))
        assert isinstance(result.confidence, BAFMarginConfidence)
        # margin = 0.7 - 0.4 = 0.3
        assert result.confidence.value == pytest.approx(0.3)

    def test_baf_margin_confidence_clamped_to_unit_interval(self) -> None:
        """BAF margin should always be in [0, 1] since winner is by max
        and strengths are in [0, 1]."""
        agg = ArgumentationAggregator(semantics=DFQuADSemantics())
        trace = (
            Trace()
            .append(_propose("p1", surface="A", confidence=1.0))
            .append(_propose("p2", surface="B", confidence=0.0))
        )
        result = asyncio.run(agg.aggregate(trace, original_question="Q?"))
        assert isinstance(result.confidence, BAFMarginConfidence)
        assert 0.0 <= result.confidence.value <= 1.0

    def test_metadata_contains_qbaf_strengths_extension(self) -> None:
        agg = ArgumentationAggregator(semantics=DFQuADSemantics())
        trace = (
            Trace()
            .append(_propose("p1", surface="A", confidence=0.4))
            .append(_propose("p2", surface="B", confidence=0.7))
        )
        result = asyncio.run(agg.aggregate(trace, original_question="Q?"))
        assert "qbaf" in result.metadata
        assert "strengths" in result.metadata
        assert "extension" in result.metadata
        # qbaf is a real QBAF
        assert isinstance(result.metadata["qbaf"], QBAF)
        # strengths is a dict[str, float]
        strengths = result.metadata["strengths"]
        assert isinstance(strengths, dict)
        assert "p1" in strengths and "p2" in strengths
        # extension is a frozenset
        assert isinstance(result.metadata["extension"], frozenset)

    def test_metadata_contains_baf_mermaid_string(self) -> None:
        """PR7/Slice C: the headline aggregator populates metadata['baf_mermaid']
        with a Mermaid flowchart string (the demo gold) computed from the
        same QBAF + strengths used for ranking."""
        agg = ArgumentationAggregator(semantics=DFQuADSemantics())
        trace = (
            Trace()
            .append(_propose("p1", surface="A", confidence=0.4))
            .append(_propose("p2", surface="B", confidence=0.7))
        )
        result = asyncio.run(agg.aggregate(trace, original_question="Q?"))
        assert "baf_mermaid" in result.metadata
        mermaid = result.metadata["baf_mermaid"]
        assert isinstance(mermaid, str)
        assert "flowchart TD" in mermaid
        # Both Propose-derived nodes should appear in the diagram
        assert "p1" in mermaid
        assert "p2" in mermaid

    def test_metadata_baf_mermaid_includes_strengths(self) -> None:
        """The aggregator's mermaid embeds strength values so the demo
        renders winner/runner-up directly."""
        agg = ArgumentationAggregator(semantics=DFQuADSemantics())
        trace = (
            Trace()
            .append(_propose("p1", surface="A", confidence=0.4))
            .append(_propose("p2", surface="B", confidence=0.7))
        )
        result = asyncio.run(agg.aggregate(trace, original_question="Q?"))
        # Strengths should appear in the Mermaid label (str=...)
        assert "str=" in result.metadata["baf_mermaid"]

    def test_metadata_contains_baf_dot_string(self) -> None:
        agg = ArgumentationAggregator(semantics=DFQuADSemantics())
        trace = (
            Trace()
            .append(_propose("p1", surface="A", confidence=0.4))
            .append(_propose("p2", surface="B", confidence=0.7))
        )
        result = asyncio.run(agg.aggregate(trace, original_question="Q?"))
        assert "baf_dot" in result.metadata
        dot = result.metadata["baf_dot"]
        assert isinstance(dot, str)
        assert "digraph QBAF" in dot
        assert "p1" in dot
        assert "p2" in dot

    def test_fallback_path_omits_visualiser_strings(self) -> None:
        """The fallback path (LastProposeFallbackAggregator on degenerate
        BAF) does not produce a meaningful QBAF, so it omits baf_mermaid
        and baf_dot from metadata."""
        agg = ArgumentationAggregator(semantics=DFQuADSemantics())
        result = asyncio.run(agg.aggregate(Trace(), original_question="Q?"))
        # Fallback path
        assert result.method == "LastProposeFallbackAggregator"
        # No visualiser strings
        assert "baf_mermaid" not in result.metadata
        assert "baf_dot" not in result.metadata

    def test_method_name_is_argumentation_aggregator(self) -> None:
        agg = ArgumentationAggregator(semantics=DFQuADSemantics())
        trace = Trace().append(_propose("p1", surface="A", confidence=0.5))
        result = asyncio.run(agg.aggregate(trace, original_question="Q?"))
        assert result.method == "ArgumentationAggregator"

    def test_single_propose_zero_margin(self) -> None:
        """One Propose, no runner-up → margin = strength - 0 = strength."""
        agg = ArgumentationAggregator(semantics=DFQuADSemantics())
        trace = Trace().append(_propose("p1", surface="A", confidence=0.7))
        result = asyncio.run(agg.aggregate(trace, original_question="Q?"))
        assert result.answer == "A"
        assert result.confidence.value == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# ArgumentationAggregator — fallback path (empty / degenerate BAF)
# ---------------------------------------------------------------------------


class TestArgumentationAggregatorFallback:
    def test_empty_trace_uses_fallback(self) -> None:
        agg = ArgumentationAggregator(semantics=DFQuADSemantics())
        result = asyncio.run(agg.aggregate(Trace(), original_question="Q?"))
        # No Proposes -> empty BAF.proposals() -> fallback path
        assert result.method == "LastProposeFallbackAggregator"
        assert isinstance(result.confidence, CopelandConfidence)

    def test_only_votes_no_proposes_uses_fallback(self) -> None:
        """Vote-only trace -> empty QBAF -> fallback (matches build_qbaf
        rule: every Propose -> Argument; Votes only boost)."""
        agg = ArgumentationAggregator(semantics=DFQuADSemantics())
        trace = Trace().append(_vote("v1", surface="X", confidence=0.5))
        result = asyncio.run(agg.aggregate(trace, original_question="Q?"))
        assert result.method == "LastProposeFallbackAggregator"

    def test_custom_fallback(self) -> None:
        """Aggregator accepts a user-supplied fallback (DI pattern)."""
        custom_fallback = LastProposeFallbackAggregator()
        agg = ArgumentationAggregator(
            semantics=DFQuADSemantics(),
            fallback=custom_fallback,
        )
        result = asyncio.run(agg.aggregate(Trace(), original_question="Q?"))
        assert result.method == "LastProposeFallbackAggregator"


# ---------------------------------------------------------------------------
# ArgumentationAggregator — semantics swap
# ---------------------------------------------------------------------------


class TestArgumentationAggregatorSemanticsSwap:
    """Different semantics produce different rankings on the same Trace
    (this is the P2 spectrum-of-semantics insight from PR4)."""

    def test_strategic_coupled_demotes_unbacked_winner(self) -> None:
        """3-agent unanimous vote without evidence; DF-QuAD admits, but
        Strategic-Coupled (with prepare(trace) recomputing evidence_backed)
        demotes."""
        # Build the T7 counterexample
        trace = Trace()
        for i, agent in enumerate(["A", "B", "C"]):
            trace = trace.append(
                _propose(f"p{i+1}", surface="X", agent_id=agent, confidence=0.7)
            )

        # DF-QuAD admits
        df_agg = ArgumentationAggregator(semantics=DFQuADSemantics())
        df_result = asyncio.run(df_agg.aggregate(trace, original_question="Q?"))
        assert df_result.answer == "X"
        df_strength = max(df_result.metadata["strengths"].values())
        assert df_strength == pytest.approx(0.7)

        # Strategic-Coupled with strict alpha demotes
        sc = StrategicCoupledSemantics(
            base=DFQuADSemantics(),
            evidence_backed=frozenset(),  # initial; prepare(trace) recomputes
            alpha=0.4,
            consensus_threshold=0.5,
        )
        sc_agg = ArgumentationAggregator(semantics=sc)
        sc_result = asyncio.run(sc_agg.aggregate(trace, original_question="Q?"))
        # sc_result still picks "X" as winner (it's the only candidate),
        # but the strength is demoted from 0.7 to 0.7 * 0.4 = 0.28
        sc_strength = max(sc_result.metadata["strengths"].values())
        assert sc_strength == pytest.approx(0.28)
        # The "X" arg is NOT in the preferred extension (below 0.5)
        ext = sc_result.metadata["extension"]
        assert ext == frozenset()


# ---------------------------------------------------------------------------
# Walton-Krabbe canonical: aggregator end-to-end
# ---------------------------------------------------------------------------


class TestWaltonKrabbeAggregator:
    def test_walton_krabbe_picks_p2_under_df_quad(self) -> None:
        """Canonical fixture: agent_a Proposes "X is true", agent_b Proposes
        "X is false", agent_b Challenges p1, agent_a Concedes p2, agent_a
        Votes for "X is true". Under DF-QuAD: p2 wins (1.0) > p1 (0.51)."""
        trace = (
            Trace()
            .append(
                _propose("p1", surface="X is true", agent_id="agent_a", confidence=0.8)
            )
            .append(
                _propose("p2", surface="X is false", agent_id="agent_b", confidence=0.6)
            )
        )
        from council.dialect.moves import Challenge

        trace = trace.append(
            Challenge(
                move_id="c1",
                agent_id="agent_b",
                round_index=1,
                target="p1",
                reason=Claim(surface="counterexample C"),
                confidence=0.7,
            )
        )
        trace = trace.append(
            Concede(
                move_id="co1",
                agent_id="agent_a",
                round_index=1,
                target="p2",
            )
        )
        trace = trace.append(
            _vote("v1", surface="X is true", agent_id="agent_a", confidence=0.9)
        )

        agg = ArgumentationAggregator(semantics=DFQuADSemantics())
        result = asyncio.run(agg.aggregate(trace, original_question="Is X?"))
        # p2 wins under DF-QuAD due to saturating combination
        assert result.answer == "X is false"
        # margin = strength(p2) - strength(p1) = 1.0 - 0.51 = 0.49
        assert isinstance(result.confidence, BAFMarginConfidence)
        assert result.confidence.value == pytest.approx(0.49, abs=0.01)


# ---------------------------------------------------------------------------
# Aggregator inherits from Aggregator ABC
# ---------------------------------------------------------------------------


class TestAggregatorBaseClass:
    def test_argumentation_aggregator_is_aggregator(self) -> None:
        from council.symbolic.argue.aggregator_base import Aggregator

        assert issubclass(ArgumentationAggregator, Aggregator)

    def test_last_propose_fallback_is_aggregator(self) -> None:
        from council.symbolic.argue.aggregator_base import Aggregator

        assert issubclass(LastProposeFallbackAggregator, Aggregator)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


class TestResultType:
    def test_argumentation_returns_aggregation_result(self) -> None:
        agg = ArgumentationAggregator(semantics=DFQuADSemantics())
        trace = Trace().append(_propose("p1", surface="X", confidence=0.5))
        result = asyncio.run(agg.aggregate(trace, original_question="Q?"))
        assert isinstance(result, AggregationResult)

    def test_fallback_returns_aggregation_result(self) -> None:
        agg = LastProposeFallbackAggregator()
        trace = Trace().append(_propose("p1", surface="X"))
        result = asyncio.run(agg.aggregate(trace, original_question="Q?"))
        assert isinstance(result, AggregationResult)
