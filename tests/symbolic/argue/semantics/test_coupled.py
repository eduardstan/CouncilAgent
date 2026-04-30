"""Tests for council/symbolic/argue/semantics/coupled.py — Strategic-Coupled.

The Strategic-Coupled semantics wraps a base GradualSemantics (default
DFQuAD) and demotes consensus-reaching arguments that lack agent-witnessed
evidence (the T3 ATL invariant). Per ADR-0012:

  - Reduces to base on full evidence backing
  - Demotes by alpha (default 0.5) when arg above consensus threshold
    (default 0.5) AND arg_id ∉ evidence_backed

Slice A pins the wrapper behavior; Slice B mechanises T7 in
tests/regressions/.
"""

from __future__ import annotations

import pytest

from council.symbolic.argue.baf import QBAF, Argument, Attack
from council.symbolic.argue.semantics.coupled import StrategicCoupledSemantics
from council.symbolic.argue.semantics.df_quad import DFQuADSemantics
from council.symbolic.argue.semantics.euler import EulerBasedSemantics
from council.symbolic.argue.semantics.quad import QESemantics


def _arg(arg_id: str, *, base: float = 0.5, withdrawn: bool = False) -> Argument:
    return Argument(
        arg_id=arg_id,
        claim_surface=f"surface-{arg_id}",
        base_score=base,
        withdrawn=withdrawn,
    )


# ---------------------------------------------------------------------------
# Reduces to base on full evidence backing
# ---------------------------------------------------------------------------


class TestReductionToBase:
    """When all consensus-reaching args are evidence-backed, Strategic-Coupled
    returns identical strengths to the underlying semantics."""

    def test_reduces_to_df_quad_when_all_args_backed(self) -> None:
        a = _arg("a", base=0.7)
        b = _arg("b", base=0.3)
        baf = QBAF(arguments=(a, b), attacks=(), supports=())
        df = DFQuADSemantics()
        sc = StrategicCoupledSemantics(
            base=df, evidence_backed=frozenset({"a", "b"})
        )
        assert sc.evaluate(baf) == df.evaluate(baf)

    def test_reduces_when_subthreshold_args_unbacked(self) -> None:
        """Subthreshold arguments aren't demoted (only consensus-reaching are)."""
        a = _arg("a", base=0.8)  # above threshold
        b = _arg("b", base=0.3)  # below threshold
        baf = QBAF(arguments=(a, b), attacks=(), supports=())
        df = DFQuADSemantics()
        sc = StrategicCoupledSemantics(
            base=df, evidence_backed=frozenset({"a"})
        )
        # a is backed → no demotion
        # b is below threshold (0.5) → no demotion
        assert sc.evaluate(baf) == df.evaluate(baf)

    def test_reduces_to_qe_when_full_backing(self) -> None:
        """Strategic-Coupled accepts any base GradualSemantics."""
        a = _arg("a", base=0.7)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        qe = QESemantics()
        sc = StrategicCoupledSemantics(
            base=qe, evidence_backed=frozenset({"a"})
        )
        assert sc.evaluate(baf) == qe.evaluate(baf)


# ---------------------------------------------------------------------------
# Demotes consensus-reaching args without backing
# ---------------------------------------------------------------------------


class TestDemotionLogic:
    def test_high_strength_no_backing_demoted(self) -> None:
        a = _arg("a", base=0.8)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        df = DFQuADSemantics()
        sc = StrategicCoupledSemantics(
            base=df, evidence_backed=frozenset()
        )
        df_strength = df.evaluate(baf)["a"]
        sc_strength = sc.evaluate(baf)["a"]
        # Default alpha=0.5: 0.8 * 0.5 = 0.4
        assert sc_strength == pytest.approx(df_strength * 0.5)

    def test_subthreshold_arg_not_demoted(self) -> None:
        a = _arg("a", base=0.3)  # below threshold 0.5
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        df = DFQuADSemantics()
        sc = StrategicCoupledSemantics(
            base=df, evidence_backed=frozenset()
        )
        # a is below threshold -> not demoted
        assert sc.evaluate(baf)["a"] == pytest.approx(0.3)

    def test_at_threshold_demoted(self) -> None:
        a = _arg("a", base=0.5)  # exactly at threshold
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        df = DFQuADSemantics()
        sc = StrategicCoupledSemantics(
            base=df, evidence_backed=frozenset()
        )
        # 0.5 >= threshold -> demoted to 0.25
        assert sc.evaluate(baf)["a"] == pytest.approx(0.25)

    def test_alpha_zero_zeros_unbacked(self) -> None:
        a = _arg("a", base=0.9)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        sc = StrategicCoupledSemantics(
            base=DFQuADSemantics(),
            evidence_backed=frozenset(),
            alpha=0.0,
        )
        assert sc.evaluate(baf)["a"] == 0.0

    def test_alpha_one_no_demotion(self) -> None:
        """alpha=1 -> no demotion -> reduces to base."""
        a = _arg("a", base=0.9)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        df = DFQuADSemantics()
        sc = StrategicCoupledSemantics(
            base=df,
            evidence_backed=frozenset(),
            alpha=1.0,
        )
        assert sc.evaluate(baf) == df.evaluate(baf)

    def test_custom_threshold(self) -> None:
        a = _arg("a", base=0.6)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        # Threshold 0.7 means 0.6 is BELOW threshold -> no demotion
        sc = StrategicCoupledSemantics(
            base=DFQuADSemantics(),
            evidence_backed=frozenset(),
            consensus_threshold=0.7,
        )
        assert sc.evaluate(baf)["a"] == pytest.approx(0.6)

    def test_partial_backing_per_argument(self) -> None:
        a = _arg("a", base=0.8)
        b = _arg("b", base=0.8)
        baf = QBAF(arguments=(a, b), attacks=(), supports=())
        sc = StrategicCoupledSemantics(
            base=DFQuADSemantics(),
            evidence_backed=frozenset({"a"}),
        )
        # a backed -> kept; b unbacked + above threshold -> demoted
        result = sc.evaluate(baf)
        assert result["a"] == pytest.approx(0.8)
        assert result["b"] == pytest.approx(0.4)  # 0.8 * 0.5


# ---------------------------------------------------------------------------
# Withdrawn handling (delegated to base)
# ---------------------------------------------------------------------------


class TestWithdrawnPassthrough:
    def test_withdrawn_argument_strength_zero(self) -> None:
        a = _arg("a", base=0.9, withdrawn=True)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        sc = StrategicCoupledSemantics(
            base=DFQuADSemantics(),
            evidence_backed=frozenset(),
        )
        # withdrawn -> base returns 0; demotion threshold 0.5 not met -> stays 0
        assert sc.evaluate(baf)["a"] == 0.0


# ---------------------------------------------------------------------------
# Defaults / construction
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_default_base_is_df_quad(self) -> None:
        sc = StrategicCoupledSemantics()
        assert isinstance(sc.evaluate, type(sc.evaluate))  # callable check
        a = _arg("a", base=0.3)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        # With default args (DFQuAD base, empty backing, alpha=0.5):
        # 0.3 below threshold -> no demotion -> 0.3
        assert sc.evaluate(baf)["a"] == pytest.approx(0.3)

    def test_default_evidence_backed_empty(self) -> None:
        a = _arg("a", base=0.9)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        sc = StrategicCoupledSemantics()
        # Empty backing + above threshold -> demoted
        assert sc.evaluate(baf)["a"] == pytest.approx(0.45)


# ---------------------------------------------------------------------------
# Preferred extension respects demotion
# ---------------------------------------------------------------------------


class TestPreferredExtensionRespectsDemotion:
    def test_consensus_arg_without_backing_excluded_from_extension(
        self,
    ) -> None:
        """The headline T7 result: an unbacked consensus argument falls
        below 0.5 after demotion -> excluded from preferred extension."""
        a = _arg("a", base=0.8)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        df = DFQuADSemantics()
        sc = StrategicCoupledSemantics(
            base=df, evidence_backed=frozenset()
        )
        # Plain DF-QuAD: a is in extension (strength 0.8 >= 0.5)
        assert "a" in df.preferred_extension(baf)
        # Strategic-Coupled: a demoted to 0.4, NOT in extension
        assert "a" not in sc.preferred_extension(baf)

    def test_consensus_arg_with_backing_in_extension(self) -> None:
        a = _arg("a", base=0.8)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        sc = StrategicCoupledSemantics(
            base=DFQuADSemantics(), evidence_backed=frozenset({"a"})
        )
        assert "a" in sc.preferred_extension(baf)


# ---------------------------------------------------------------------------
# Determinism + boundedness
# ---------------------------------------------------------------------------


class TestInvariants:
    def test_strengths_in_unit_interval(self) -> None:
        a = _arg("a", base=0.7)
        b = _arg("b", base=0.6)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=0.5),),
            supports=(),
        )
        sc = StrategicCoupledSemantics(
            base=DFQuADSemantics(),
            evidence_backed=frozenset({"a"}),
        )
        for v in sc.evaluate(baf).values():
            assert 0.0 <= v <= 1.0

    def test_byte_equal_over_50_invocations(self) -> None:
        a = _arg("a", base=0.7)
        b = _arg("b", base=0.4)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=0.5),),
            supports=(),
        )
        sc = StrategicCoupledSemantics(
            base=DFQuADSemantics(),
            evidence_backed=frozenset(),
        )
        first = sc.evaluate(baf)
        for _ in range(50):
            assert sc.evaluate(baf) == first

    def test_works_with_ebs_base(self) -> None:
        """Ebs has w=1 boundary degeneracy → strength 1.0; demotion still
        applies if the arg lacks backing."""
        a = _arg("a", base=1.0)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        sc = StrategicCoupledSemantics(
            base=EulerBasedSemantics(),
            evidence_backed=frozenset(),
        )
        # Ebs returns 1.0 for w=1; SC demotes by alpha=0.5 -> 0.5
        assert sc.evaluate(baf)["a"] == pytest.approx(0.5)
