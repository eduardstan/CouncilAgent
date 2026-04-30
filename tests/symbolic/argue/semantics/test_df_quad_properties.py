"""Slice B tests for DF-QuAD: Walton-Krabbe golden + Rago 2016 properties.

Pins behaviour required by P2 (AAAI 2027) reviewer-bait:
  - Walton-Krabbe canonical golden strengths
  - Monotonicity in source strength (Rago 2016 Proposition 3)
  - Symmetric: replacing with lower strength does not raise (Proposition 4)
  - Adding zero-strength edge has no effect (Proposition 6)
  - Adding max-strength supporter saturates (Proposition 7)
  - Continuity (Theorem 1, the discontinuity-freeness property)
  - Determinism (byte-equal across runs)
  - Order independence (Proposition 2)
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from council.dialect.parsers import parse_move
from council.dialect.trace import Trace
from council.symbolic.argue.baf import QBAF, Argument, Attack, Support
from council.symbolic.argue.builders import build_qbaf
from council.symbolic.argue.semantics.df_quad import DFQuADSemantics

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _arg(arg_id: str, *, base: float = 0.5) -> Argument:
    return Argument(arg_id=arg_id, claim_surface=arg_id, base_score=base)


# ---------------------------------------------------------------------------
# Walton-Krabbe canonical golden strengths
# ---------------------------------------------------------------------------


def _load_walton_krabbe_baf() -> QBAF:
    raw = (FIXTURES_DIR / "walton_krabbe.json").read_text()
    fixture = json.loads(raw)
    trace = Trace()
    for entry in fixture["trace"]:
        move = parse_move(
            json.dumps(entry["json"]),
            agent_id=entry["agent_id"],
            round_index=entry["round_index"],
            move_id=entry["move_id"],
        )
        trace = trace.append(move)
    return build_qbaf(trace)


class TestWaltonKrabbeStrengths:
    """Closed-form expected DF-QuAD strengths derived by hand from the fixture.

    p1 (base=1.0, attacked by c1 with weight=0.7):
      strength(c1) = 0.7 (no edges)
      contribution = 0.7 * 0.7 = 0.49
      v_a = F([0.49]) = 0.49
      v_s = 0
      c(1.0, 0.49, 0) = 1.0 - 1.0 * 0.49 = 0.51
    p2 (base=0.6, supported by co1 with weight=1.0):
      strength(co1) = 1.0
      contribution = 1.0 * 1.0 = 1.0
      v_a = 0; v_s = 1.0
      c(0.6, 0, 1.0) = 0.6 + (1-0.6)*1.0 = 1.0
    c1: base=0.7; no edges; strength = 0.7
    co1: base=1.0; no edges; strength = 1.0
    """

    def test_p1_strength_reduced_by_challenge(self) -> None:
        baf = _load_walton_krabbe_baf()
        sem = DFQuADSemantics()
        strengths = sem.evaluate(baf)
        assert strengths["p1"] == pytest.approx(0.51)

    def test_p2_strength_boosted_by_concession_to_max(self) -> None:
        baf = _load_walton_krabbe_baf()
        sem = DFQuADSemantics()
        strengths = sem.evaluate(baf)
        assert strengths["p2"] == pytest.approx(1.0)

    def test_c1_strength_equals_base(self) -> None:
        baf = _load_walton_krabbe_baf()
        sem = DFQuADSemantics()
        strengths = sem.evaluate(baf)
        assert strengths["c1"] == pytest.approx(0.7)

    def test_co1_strength_equals_base(self) -> None:
        baf = _load_walton_krabbe_baf()
        sem = DFQuADSemantics()
        strengths = sem.evaluate(baf)
        assert strengths["co1"] == pytest.approx(1.0)

    def test_winner_is_p2_after_concession(self) -> None:
        # Strengths: p1=0.51, p2=1.0, c1=0.7, co1=1.0
        # The aggregator (PR6) picks the highest-strength Propose. p2 wins.
        baf = _load_walton_krabbe_baf()
        sem = DFQuADSemantics()
        strengths = sem.evaluate(baf)
        proposals = baf.proposals()
        winner = max(proposals, key=lambda a: strengths[a.arg_id])
        assert winner.arg_id == "p2"

    def test_walton_krabbe_preferred_extension(self) -> None:
        baf = _load_walton_krabbe_baf()
        sem = DFQuADSemantics()
        ext = sem.preferred_extension(baf)
        # p1 (0.51), c1 (0.7), co1 (1.0), p2 (1.0) all >= 0.5 → all included
        assert ext == frozenset({"p1", "p2", "c1", "co1"})


# ---------------------------------------------------------------------------
# Monotonicity (Rago 2016 Proposition 3, 4)
# ---------------------------------------------------------------------------


class TestMonotonicityProposition3:
    """Replacing a supporter with a stronger one does not decrease the target's
    strength. Replacing an attacker with a weaker one does not decrease it.
    """

    def test_increasing_supporter_strength_increases_target(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.3)
        results = []
        for b_base in [0.1, 0.3, 0.5, 0.7, 0.9]:
            b = _arg("b", base=b_base)
            baf = QBAF(
                arguments=(a, b),
                attacks=(),
                supports=(Support(source="b", target="a", weight=1.0),),
            )
            results.append(sem.evaluate(baf)["a"])
        # Each successive base score for b should produce >= previous strength
        for i in range(1, len(results)):
            assert results[i] >= results[i - 1] - 1e-9, (
                f"monotonicity violated: {results}"
            )

    def test_increasing_attacker_strength_decreases_target(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.9)
        results = []
        for b_base in [0.0, 0.2, 0.4, 0.6, 0.8]:
            b = _arg("b", base=b_base)
            baf = QBAF(
                arguments=(a, b),
                attacks=(Attack(source="b", target="a", weight=1.0),),
                supports=(),
            )
            results.append(sem.evaluate(baf)["a"])
        # strength(a) should monotonically DECREASE as attacker strength grows
        for i in range(1, len(results)):
            assert results[i] <= results[i - 1] + 1e-9, (
                f"monotonicity violated: {results}"
            )

    def test_increasing_attack_weight_decreases_target(self) -> None:
        """W2 extension: monotone in edge weight too."""
        sem = DFQuADSemantics()
        a = _arg("a", base=1.0)
        b = _arg("b", base=1.0)
        results = []
        for w in [0.0, 0.25, 0.5, 0.75, 1.0]:
            baf = QBAF(
                arguments=(a, b),
                attacks=(Attack(source="b", target="a", weight=w),),
                supports=(),
            )
            results.append(sem.evaluate(baf)["a"])
        for i in range(1, len(results)):
            assert results[i] <= results[i - 1] + 1e-9


# ---------------------------------------------------------------------------
# Order independence (Rago 2016 Proposition 2)
# ---------------------------------------------------------------------------


class TestOrderIndependence:
    def test_argument_order_does_not_affect_strengths(self) -> None:
        """Reorder arguments in QBAF; strengths must be the same dict."""
        sem = DFQuADSemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.4)
        c = _arg("c", base=0.6)
        baf1 = QBAF(
            arguments=(a, b, c),
            attacks=(Attack(source="b", target="a", weight=0.7),),
            supports=(Support(source="c", target="a", weight=0.5),),
        )
        baf2 = QBAF(
            arguments=(c, a, b),  # different order
            attacks=(Attack(source="b", target="a", weight=0.7),),
            supports=(Support(source="c", target="a", weight=0.5),),
        )
        s1 = sem.evaluate(baf1)
        s2 = sem.evaluate(baf2)
        assert s1 == s2

    def test_attack_edge_order_does_not_affect_strengths(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=1.0)
        b = _arg("b", base=0.5)
        c = _arg("c", base=0.4)
        e1 = Attack(source="b", target="a", weight=1.0)
        e2 = Attack(source="c", target="a", weight=1.0)
        baf1 = QBAF(arguments=(a, b, c), attacks=(e1, e2), supports=())
        baf2 = QBAF(arguments=(a, b, c), attacks=(e2, e1), supports=())
        assert sem.evaluate(baf1) == sem.evaluate(baf2)


# ---------------------------------------------------------------------------
# Saturation and zero-effect (Propositions 6, 7)
# ---------------------------------------------------------------------------


class TestSaturationAndZero:
    def test_max_strength_supporter_saturates_target(self) -> None:
        """Proposition 7 in Rago 2016: a max-strength supporter saturates F."""
        sem = DFQuADSemantics()
        a = _arg("a", base=0.0)
        b = _arg("b", base=1.0)
        baf = QBAF(
            arguments=(a, b),
            attacks=(),
            supports=(Support(source="b", target="a", weight=1.0),),
        )
        # v_s = F([1.0]) = 1.0; v_a = 0; c(0, 0, 1.0) = 0 + 1*1 = 1.0
        assert sem.evaluate(baf)["a"] == pytest.approx(1.0)

    def test_max_strength_attacker_saturates_target(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=1.0)
        b = _arg("b", base=1.0)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        # v_a = 1.0; c(1.0, 1.0, 0) = 1.0 - 1.0 = 0.0
        assert sem.evaluate(baf)["a"] == pytest.approx(0.0)

    def test_adding_isolated_argument_does_not_change_others(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.7)
        b = _arg("b", base=0.4)
        baf_small = QBAF(arguments=(a,), attacks=(), supports=())
        baf_large = QBAF(arguments=(a, b), attacks=(), supports=())
        assert sem.evaluate(baf_small)["a"] == sem.evaluate(baf_large)["a"]


# ---------------------------------------------------------------------------
# Continuity (Theorem 1: discontinuity-freeness)
# ---------------------------------------------------------------------------


class TestContinuityTheorem1:
    """As epsilon -> 0+, adding an attacker/supporter with strength epsilon
    converges to the no-edge result (Theorem 1 in Rago 2016 — the discontinuity-
    freeness theorem that gives DF-QuAD its name).
    """

    def test_vanishing_attacker_strength_recovers_no_attack(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.7)
        baseline = sem.evaluate(QBAF(arguments=(a,), attacks=(), supports=()))["a"]

        # Sequence of decreasing epsilon
        for eps in [0.1, 0.01, 0.001, 0.0001]:
            b = _arg("b", base=eps)
            baf = QBAF(
                arguments=(a, b),
                attacks=(Attack(source="b", target="a", weight=1.0),),
                supports=(),
            )
            actual = sem.evaluate(baf)["a"]
            # strength approaches baseline as eps -> 0
            assert abs(actual - baseline) <= eps + 1e-9, (
                f"discontinuity at eps={eps}: |{actual} - {baseline}| > eps"
            )

    def test_vanishing_supporter_strength_recovers_no_support(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.3)
        baseline = sem.evaluate(QBAF(arguments=(a,), attacks=(), supports=()))["a"]

        for eps in [0.1, 0.01, 0.001, 0.0001]:
            b = _arg("b", base=eps)
            baf = QBAF(
                arguments=(a, b),
                attacks=(),
                supports=(Support(source="b", target="a", weight=1.0),),
            )
            actual = sem.evaluate(baf)["a"]
            assert abs(actual - baseline) <= eps + 1e-9


# ---------------------------------------------------------------------------
# Determinism — byte-equal across runs
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_walton_krabbe_byte_equal_over_100_invocations(self) -> None:
        baf = _load_walton_krabbe_baf()
        sem = DFQuADSemantics()
        first = sem.evaluate(baf)
        for _ in range(100):
            assert sem.evaluate(baf) == first

    def test_complex_baf_byte_equal_over_50_invocations(self) -> None:
        random.seed(0)  # used for the random fixture below; result still deterministic
        sem = DFQuADSemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.4)
        c = _arg("c", base=0.7)
        d = _arg("d", base=0.3)
        baf = QBAF(
            arguments=(a, b, c, d),
            attacks=(
                Attack(source="b", target="a", weight=0.6),
                Attack(source="d", target="c", weight=0.4),
            ),
            supports=(
                Support(source="c", target="a", weight=0.5),
            ),
        )
        first = sem.evaluate(baf)
        for _ in range(50):
            assert sem.evaluate(baf) == first

    def test_strengths_are_pure_floats(self) -> None:
        sem = DFQuADSemantics()
        a = _arg("a", base=0.5)
        b = _arg("b", base=0.4)
        baf = QBAF(
            arguments=(a, b),
            attacks=(Attack(source="b", target="a", weight=0.7),),
            supports=(),
        )
        result = sem.evaluate(baf)
        for v in result.values():
            assert isinstance(v, float)
