"""Tests for council/symbolic/argue/semantics/df_quad.py — DF-QuAD semantics.

DF-QuAD is the Rago-Toni-Aurisicchio-Baroni (KR 2016) gradual semantics.
The W2 generalisation supports weighted edges (Attack.weight,
Support.weight in [0, 1]) and withdrawn arguments per ADR-0010.

Slice A pins the core algorithm: F aggregation (Lemma 1 closed form),
combination function c (Equations 19/20), recursive evaluation, withdrawn
handling, cycle detection, preferred-extension threshold.
Slice B adds Walton-Krabbe golden + monotonicity + continuity + determinism.
Slice C uses the semantics in T4 (Borda recovery, tests/regressions/).
"""

from __future__ import annotations

import math

import pytest

from council.symbolic.argue.baf import QBAF, Argument, Attack, Support
from council.symbolic.argue.semantics.df_quad import DFQuADSemantics


def _arg(arg_id: str, *, base: float = 0.5, withdrawn: bool = False) -> Argument:
    return Argument(
        arg_id=arg_id,
        claim_surface=f"surface-{arg_id}",
        base_score=base,
        withdrawn=withdrawn,
    )


# ---------------------------------------------------------------------------
# Empty / degenerate cases
# ---------------------------------------------------------------------------


class TestDFQuADEmpty:
    def test_empty_qbaf_returns_empty_dict(self) -> None:
        sem = DFQuADSemantics()
        assert sem.evaluate(QBAF(arguments=(), attacks=(), supports=())) == {}

    def test_single_unattacked_argument_strength_equals_base(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.7)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert sem.evaluate(baf) == {"a": 0.7}

    def test_returns_dict_keyed_by_arg_id(self) -> None:
        sem = DFQuADSemantics()
        baf = QBAF(
            arguments=(_arg("a", base=0.3), _arg("b", base=0.6)),
            attacks=(),
            supports=(),
        )
        result = sem.evaluate(baf)
        assert set(result.keys()) == {"a", "b"}


# ---------------------------------------------------------------------------
# Combination function c — Equations 19, 20 in Rago 2016
# ---------------------------------------------------------------------------


class TestCombinationFunction:
    """Direct exercises of c(v0, v_a, v_s) via no-edge / single-edge graphs.

    c(v0, v_a, v_s) = v0 - v0 * |v_s - v_a|         if v_a >= v_s
                    = v0 + (1 - v0) * |v_s - v_a|   if v_a < v_s
    """

    def test_c_no_attackers_no_supporters_returns_base(self) -> None:
        sem = DFQuADSemantics()
        baf = QBAF(arguments=(_arg("a", base=0.42),), attacks=(), supports=())
        # v_a = F(()) = 0, v_s = 0, c(0.42, 0, 0) = 0.42 (v_a >= v_s, |0|*0.42=0)
        assert sem.evaluate(baf)["a"] == pytest.approx(0.42)

    def test_c_with_attacker_only_attacker_dominant(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=1.0)
        b = _arg("b", base=0.5)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        # strength(b) = base(b) = 0.5 (no edges into b)
        # contribution to a from b = weight * strength(b) = 1.0 * 0.5 = 0.5
        # v_a = F([0.5]) = 0.5
        # v_s = F([]) = 0
        # v_a >= v_s, c(1.0, 0.5, 0) = 1.0 - 1.0 * |0 - 0.5| = 0.5
        assert sem.evaluate(baf)["a"] == pytest.approx(0.5)

    def test_c_with_supporter_only_supporter_dominant(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.6)
        b = _arg("b", base=0.5)
        baf = QBAF(
            arguments=(a, b),
            attacks=(),
            supports=(Support(source="b", target="a", weight=1.0),),
        )
        # v_a = 0, v_s = 0.5
        # v_a < v_s, c(0.6, 0, 0.5) = 0.6 + (1-0.6) * |0.5 - 0| = 0.6 + 0.2 = 0.8
        assert sem.evaluate(baf)["a"] == pytest.approx(0.8)

    def test_c_balanced_attack_and_support(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.4)
        c = _arg("c", base=0.4)
        baf = QBAF(
            arguments=(a, b, c),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(Support(source="c", target="a", weight=1.0),),
        )
        # v_a = 0.4, v_s = 0.4 -> |v_s - v_a| = 0 -> c = base = 0.5
        assert sem.evaluate(baf)["a"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# F aggregation function — Lemma 1 closed form
# ---------------------------------------------------------------------------


class TestStrengthAggregationLemma1:
    """F(v_1, ..., v_n) = 1 - prod(1 - v_i)."""

    def test_aggregation_two_attackers(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=1.0)
        b = _arg("b", base=0.6)
        c = _arg("c", base=0.4)
        baf = QBAF(
            arguments=(a, b, c),
            attacks=(
                Attack(source="b", target="a", weight=1.0),
                Attack(source="c", target="a", weight=1.0),
            ),
            supports=(),
        )
        # v_a = F([0.6, 0.4]) = 1 - (1-0.6)(1-0.4) = 1 - 0.4*0.6 = 0.76
        # v_s = 0
        # c(1.0, 0.76, 0) = 1.0 - 1.0 * 0.76 = 0.24
        assert sem.evaluate(baf)["a"] == pytest.approx(0.24)

    def test_aggregation_three_supporters(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.0)
        b = _arg("b", base=0.5)
        c = _arg("c", base=0.5)
        d = _arg("d", base=0.5)
        baf = QBAF(
            arguments=(a, b, c, d),
            attacks=(),
            supports=(
                Support(source="b", target="a", weight=1.0),
                Support(source="c", target="a", weight=1.0),
                Support(source="d", target="a", weight=1.0),
            ),
        )
        # v_s = F([0.5, 0.5, 0.5]) = 1 - (0.5)^3 = 0.875
        # v_a = 0
        # c(0, 0, 0.875) = 0 + (1-0) * 0.875 = 0.875
        assert sem.evaluate(baf)["a"] == pytest.approx(0.875)

    def test_zero_strength_edge_has_no_effect(self) -> None:
        """Proposition 6 in Rago 2016: F(S U {0}) = F(S)."""
        sem = DFQuADSemantics()
        a = _arg("a", base=0.7)
        b = _arg("b", base=0.0)  # zero-strength attacker
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        assert sem.evaluate(baf)["a"] == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Edge weights (W2 extension over Rago 2016)
# ---------------------------------------------------------------------------


class TestEdgeWeights:
    """Edge weights modulate the contribution: contribution = weight * strength(source).

    This is the W2 extension (ADR-0010 Q1). Reduces to unweighted DF-QuAD
    when all weights = 1.
    """

    def test_attack_weight_zero_has_no_effect(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=1.0)
        b = _arg("b", base=0.5)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=0.0),),
            supports=(),
        )
        # contribution = 0.0 * 0.5 = 0; v_a = 0; strength = base = 1.0
        assert sem.evaluate(baf)["a"] == pytest.approx(1.0)

    def test_attack_weight_half_dampens_effect(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=1.0)
        b = _arg("b", base=1.0)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=0.5),),
            supports=(),
        )
        # contribution = 0.5 * 1.0 = 0.5; v_a = 0.5; v_s = 0
        # c(1.0, 0.5, 0) = 1.0 - 0.5 = 0.5
        assert sem.evaluate(baf)["a"] == pytest.approx(0.5)

    def test_unweighted_reduction_all_weights_one(self) -> None:
        """When all weights are 1, the result equals the Rago 2016 unweighted DF-QuAD."""
        sem = DFQuADSemantics()
        a = _arg("a", base=0.6)
        b = _arg("b", base=0.4)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        # Standard DF-QuAD: c(0.6, 0.4, 0) = 0.6 - 0.6 * 0.4 = 0.36
        assert sem.evaluate(baf)["a"] == pytest.approx(0.36)


# ---------------------------------------------------------------------------
# Withdrawn argument handling (ADR-0010 Q2)
# ---------------------------------------------------------------------------


class TestWithdrawnHandling:
    def test_withdrawn_argument_strength_is_zero(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.9, withdrawn=True)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert sem.evaluate(baf)["a"] == 0.0

    def test_withdrawn_attacker_contributes_zero(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=1.0)
        b = _arg("b", base=1.0, withdrawn=True)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        # b is withdrawn, contributes 0 -> strength(a) = base = 1.0
        assert sem.evaluate(baf)["a"] == pytest.approx(1.0)

    def test_withdrawn_supporter_contributes_zero(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.3)
        b = _arg("b", base=1.0, withdrawn=True)
        baf = QBAF(
            arguments=(a, b),
            attacks=(),
            supports=(Support(source="b", target="a", weight=1.0),),
        )
        # b is withdrawn, contributes 0 -> strength(a) = base = 0.3
        assert sem.evaluate(baf)["a"] == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Cycle detection (ADR-0010 Q3)
# ---------------------------------------------------------------------------


class TestCycleDetection:
    def test_two_cycle_raises_value_error(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.5)
        baf = QBAF(
            arguments=(a, b),
            attacks=(
                Attack(source="a", target="b", weight=1.0),
                Attack(source="b", target="a", weight=1.0),
            ),
            supports=(),
        )
        with pytest.raises(ValueError, match="cycle"):
            sem.evaluate(baf)

    def test_three_cycle_via_supports_raises(self) -> None:
        sem = DFQuADSemantics()
        a, b, c = _arg("a"), _arg("b"), _arg("c")
        baf = QBAF(
            arguments=(a, b, c),
            attacks=(),
            supports=(
                Support(source="a", target="b", weight=1.0),
                Support(source="b", target="c", weight=1.0),
                Support(source="c", target="a", weight=1.0),
            ),
        )
        with pytest.raises(ValueError, match="cycle"):
            sem.evaluate(baf)

    def test_dag_no_error(self) -> None:
        sem = DFQuADSemantics()
        a, b, c = _arg("a"), _arg("b"), _arg("c")
        baf = QBAF(
            arguments=(a, b, c),
            attacks=(
                Attack(source="b", target="a", weight=1.0),
                Attack(source="c", target="b", weight=1.0),
            ),
            supports=(),
        )
        # Linear chain, no cycle — must succeed
        result = sem.evaluate(baf)
        assert set(result.keys()) == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# Preferred extension (ADR-0010 Q4)
# ---------------------------------------------------------------------------


class TestPreferredExtension:
    def test_returns_frozenset(self) -> None:
        sem = DFQuADSemantics()
        baf = QBAF(arguments=(), attacks=(), supports=())
        ext = sem.preferred_extension(baf)
        assert isinstance(ext, frozenset)

    def test_high_strength_argument_in_extension(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.8)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert "a" in sem.preferred_extension(baf)

    def test_low_strength_argument_not_in_extension(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.2)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert "a" not in sem.preferred_extension(baf)

    def test_at_threshold_is_included(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.5)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        # Threshold is 0.5 inclusive
        assert "a" in sem.preferred_extension(baf)

    def test_withdrawn_excluded_from_extension(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.9, withdrawn=True)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        # Withdrawn argument cannot be in the preferred extension regardless of strength
        assert "a" not in sem.preferred_extension(baf)

    def test_attacked_argument_below_threshold_excluded(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=1.0)
        b = _arg("b", base=1.0)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        # strength(a) = c(1.0, 1.0, 0) = 1.0 - 1.0 * 1.0 = 0.0 -> excluded
        # strength(b) = 1.0 -> included
        ext = sem.preferred_extension(baf)
        assert ext == frozenset({"b"})


# ---------------------------------------------------------------------------
# Sanity: returned strengths are in [0, 1] (DF-QuAD bounded by Proposition 1)
# ---------------------------------------------------------------------------


class TestStrengthsInUnitInterval:
    def test_all_strengths_in_unit_interval(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.7)
        b = _arg("b", base=0.6)
        c = _arg("c", base=0.4)
        baf = QBAF(
            arguments=(a, b, c),
            attacks=(Attack(source="c", target="a", weight=0.7),),
            supports=(Support(source="b", target="a", weight=0.5),),
        )
        result = sem.evaluate(baf)
        for v in result.values():
            assert 0.0 <= v <= 1.0
            assert math.isfinite(v)
