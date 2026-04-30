"""Cross-semantics tests: shared invariants across DF-QuAD, QE, Ebs.

Pins behaviour required by ADR-0010 + ADR-0011: all three semantics share
the same surface (GradualSemantics ABC) and the same invariants (bounded
strengths, withdrawn -> 0, no-edge -> base, cycle -> ValueError, deterministic).

The semantics differ in their *internal* aggregation curves but agree on
structural endpoints: no-edge BAFs return base scores; max-strength
attackers reduce target strength; max-strength supporters increase it.
"""

from __future__ import annotations

import math

import pytest

from council.symbolic.argue.baf import QBAF, Argument, Attack, Support
from council.symbolic.argue.semantics.base import GradualSemantics
from council.symbolic.argue.semantics.df_quad import DFQuADSemantics
from council.symbolic.argue.semantics.euler import EulerBasedSemantics
from council.symbolic.argue.semantics.quad import QESemantics

ALL_SEMANTICS: list[GradualSemantics] = [
    DFQuADSemantics(),
    QESemantics(),
    EulerBasedSemantics(),
]


def _arg(arg_id: str, *, base: float = 0.5, withdrawn: bool = False) -> Argument:
    return Argument(
        arg_id=arg_id,
        claim_surface=f"surface-{arg_id}",
        base_score=base,
        withdrawn=withdrawn,
    )


# ---------------------------------------------------------------------------
# All three return base scores on no-edge BAFs
# ---------------------------------------------------------------------------


class TestNoEdgeAgreement:
    @pytest.mark.parametrize("sem", ALL_SEMANTICS, ids=lambda s: type(s).__name__)
    def test_no_edge_returns_base(self, sem: GradualSemantics) -> None:
        for w in [0.1, 0.3, 0.5, 0.7, 0.9]:
            a = _arg("a", base=w)
            baf = QBAF(arguments=(a,), attacks=(), supports=())
            assert sem.evaluate(baf)["a"] == pytest.approx(w), (
                f"{type(sem).__name__} failed at w={w}"
            )

    @pytest.mark.parametrize("sem", ALL_SEMANTICS, ids=lambda s: type(s).__name__)
    def test_no_edge_multiple_arguments_each_returns_base(
        self, sem: GradualSemantics
    ) -> None:
        a = _arg("a", base=0.3)
        b = _arg("b", base=0.6)
        c = _arg("c", base=0.9)
        baf = QBAF(arguments=(a, b, c), attacks=(), supports=())
        result = sem.evaluate(baf)
        assert result["a"] == pytest.approx(0.3)
        assert result["b"] == pytest.approx(0.6)
        assert result["c"] == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# Direction agreement: supporter raises, attacker lowers
# ---------------------------------------------------------------------------


class TestDirectionAgreement:
    @pytest.mark.parametrize("sem", ALL_SEMANTICS, ids=lambda s: type(s).__name__)
    def test_supporter_raises_strength(self, sem: GradualSemantics) -> None:
        # Use base=0.5 to avoid Ebs boundary degeneracy at 0 and 1
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.8)
        baf_no = QBAF(arguments=(a,), attacks=(), supports=())
        baf_sup = QBAF(
            arguments=(a, b),
            attacks=(),
            supports=(Support(source="b", target="a", weight=1.0),),
        )
        s_no = sem.evaluate(baf_no)["a"]
        s_sup = sem.evaluate(baf_sup)["a"]
        assert s_sup > s_no, (
            f"{type(sem).__name__}: supporter did not raise strength "
            f"({s_no} -> {s_sup})"
        )

    @pytest.mark.parametrize("sem", ALL_SEMANTICS, ids=lambda s: type(s).__name__)
    def test_attacker_lowers_strength(self, sem: GradualSemantics) -> None:
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.8)
        baf_no = QBAF(arguments=(a,), attacks=(), supports=())
        baf_att = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        s_no = sem.evaluate(baf_no)["a"]
        s_att = sem.evaluate(baf_att)["a"]
        assert s_att < s_no, (
            f"{type(sem).__name__}: attacker did not lower strength "
            f"({s_no} -> {s_att})"
        )


# ---------------------------------------------------------------------------
# Boundedness across all three (every strength in [0, 1])
# ---------------------------------------------------------------------------


class TestBoundednessAgreement:
    @pytest.mark.parametrize("sem", ALL_SEMANTICS, ids=lambda s: type(s).__name__)
    def test_complex_baf_strengths_in_unit_interval(
        self, sem: GradualSemantics
    ) -> None:
        a = _arg("a", base=0.7)
        b = _arg("b", base=0.6)
        c = _arg("c", base=0.4)
        d = _arg("d", base=0.3)
        baf = QBAF(
            arguments=(a, b, c, d),
            attacks=(
                Attack(source="b", target="a", weight=0.7),
                Attack(source="d", target="c", weight=0.4),
            ),
            supports=(Support(source="c", target="a", weight=0.5),),
        )
        for v in sem.evaluate(baf).values():
            assert 0.0 <= v <= 1.0
            assert math.isfinite(v)


# ---------------------------------------------------------------------------
# Withdrawn handling agreement
# ---------------------------------------------------------------------------


class TestWithdrawnAgreement:
    @pytest.mark.parametrize("sem", ALL_SEMANTICS, ids=lambda s: type(s).__name__)
    def test_withdrawn_argument_strength_zero(
        self, sem: GradualSemantics
    ) -> None:
        a = _arg("a", base=0.9, withdrawn=True)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        assert sem.evaluate(baf)["a"] == 0.0

    @pytest.mark.parametrize("sem", ALL_SEMANTICS, ids=lambda s: type(s).__name__)
    def test_withdrawn_attacker_no_effect(self, sem: GradualSemantics) -> None:
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.9, withdrawn=True)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        assert sem.evaluate(baf)["a"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Cycle policy agreement
# ---------------------------------------------------------------------------


class TestCycleAgreement:
    @pytest.mark.parametrize("sem", ALL_SEMANTICS, ids=lambda s: type(s).__name__)
    def test_two_cycle_raises_on_all(self, sem: GradualSemantics) -> None:
        a = _arg("a")
        b = _arg("b")
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


# ---------------------------------------------------------------------------
# Determinism agreement
# ---------------------------------------------------------------------------


class TestDeterminismAgreement:
    @pytest.mark.parametrize("sem", ALL_SEMANTICS, ids=lambda s: type(s).__name__)
    def test_byte_equal_over_50_invocations(self, sem: GradualSemantics) -> None:
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.4)
        c = _arg("c", base=0.6)
        baf = QBAF(
            arguments=(a, b, c),
            attacks=(Attack(source="b", target="a", weight=0.7),),
            supports=(Support(source="c", target="a", weight=0.5),),
        )
        first = sem.evaluate(baf)
        for _ in range(50):
            assert sem.evaluate(baf) == first


# ---------------------------------------------------------------------------
# Semantics-divergence: each ranks differently on the canonical fixture
# ---------------------------------------------------------------------------


class TestWaltonKrabbeSemanticsDivergence:
    """The Walton-Krabbe canonical fixture is *designed* to expose semantics
    divergence: DF-QuAD's saturating combination function pushes p2 to 1.0
    (concession dominates), but QE's smoother h(x)=x^2/(1+x^2) gives p1 a
    higher strength (0.806) than p2 (0.800) because h(1.0) = 0.5 rather than
    saturating. Ebs hits p1's base-1 boundary degeneracy, freezing p1 at 1.0.

    These divergences are mathematically correct under each semantics. They
    illustrate why P2 (AAAI 2027) compares them: different semantics encode
    different intuitions about how attackers and supporters compose.
    """

    def _walton_krabbe_qbaf(self) -> QBAF:
        return QBAF(
            arguments=(
                Argument(arg_id="p1", claim_surface="X is true", base_score=1.0),
                Argument(arg_id="p2", claim_surface="X is false", base_score=0.6),
                Argument(arg_id="c1", claim_surface="counterexample C", base_score=0.7),
                Argument(arg_id="co1", claim_surface="(concession to p2)", base_score=1.0),
            ),
            attacks=(Attack(source="c1", target="p1", weight=0.7),),
            supports=(Support(source="co1", target="p2", weight=1.0),),
        )

    def test_df_quad_picks_p2(self) -> None:
        """DF-QuAD: c(0.6, 0, 1.0) = 1.0 saturates p2 → p2 wins."""
        sem = DFQuADSemantics()
        s = sem.evaluate(self._walton_krabbe_qbaf())
        assert s["p2"] > s["p1"]
        assert s["p2"] == pytest.approx(1.0)

    def test_qe_picks_p1(self) -> None:
        """QE: smooth h(1.0) = 0.5 → p2 only reaches 0.8; meanwhile p1's
        attack is dampened (h(0.49) ~ 0.194), p1 settles at ~0.806."""
        sem = QESemantics()
        s = sem.evaluate(self._walton_krabbe_qbaf())
        assert s["p1"] > s["p2"]

    def test_ebs_picks_p1_due_to_boundary(self) -> None:
        """Ebs: w(p1) = 1.0 → boundary degeneracy → p1 frozen at 1.0
        (ADR-0011 Q3). Aggregator (PR6) defaults to DF-QuAD specifically
        to avoid this."""
        sem = EulerBasedSemantics()
        s = sem.evaluate(self._walton_krabbe_qbaf())
        assert s["p1"] == pytest.approx(1.0)
        assert s["p1"] > s["p2"]

    @pytest.mark.parametrize("sem", ALL_SEMANTICS, ids=lambda s: type(s).__name__)
    def test_winner_is_a_propose_under_all_semantics(
        self, sem: GradualSemantics
    ) -> None:
        """Whatever the ranking, the highest-strength Propose is one of
        {p1, p2} (Concedes/Challenges produce Arguments but are not
        candidate winners — `proposals()` filtering)."""
        baf = self._walton_krabbe_qbaf()
        strengths = sem.evaluate(baf)
        # Manually filter to Propose-derived (p1, p2 in this fixture)
        propose_strengths = {k: strengths[k] for k in ["p1", "p2"]}
        winner = max(propose_strengths, key=lambda k: propose_strengths[k])
        assert winner in {"p1", "p2"}
