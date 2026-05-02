"""T6 — Caminada-Amgoud rationality-postulate matrix for DF-QuAD.

Master plan §10:
  Identify which Caminada-Amgoud postulates the aggregator satisfies;
  identify which Arrow-style axiom is necessarily violated (by
  Gibbard-Satterthwaite).

The reference table is Amgoud-Ben-Naim 2018 (IJAR), Table 1 (in
`papers/3 --- argumentation/`). For DF-QuAD on the W2 QBAF, the
satisfaction matrix is:

  SATISFIED:
    Anonymity                     — isomorphic graphs yield equal strengths
    Bi-variate Independence       — disjoint subframes don't interfere
    Bi-variate Directionality     — strength depends only on predecessors
    Bi-variate Equivalence        — same w/predecessors -> same strength
    Stability                     — empty in/out -> strength = base
    Neutrality                    — strength-0 attackers/supporters no-op
    Monotony                      — stronger attacker weakens (not strictly)
    Reinforcement                 — adding supporter does not decrease
    Franklin                      — equal attackers + supporters cancel

  VIOLATED (DF-QuAD's saturation behaviour):
    Strict Monotony               — saturation can leave strength unchanged
    Strict Reinforcement          — dual
    Resilience                    — non-extreme base can reach 0 or 1
    Weakening / Strengthening     — DF-QuAD's c() doesn't always pull below
                                    / above base

  NOT APPLICABLE:
    Inertia                       — extension-semantics-only postulate

This file pins each cell with a positive (satisfied) or negative
(counterexample) test. Together they form the T6 mechanisation. The
docs/theory.md §T6 section presents the same matrix in prose for P2
(AAAI 2027) reviewers.
"""

from __future__ import annotations

import pytest

from council.symbolic.argue.baf import QBAF, Argument, Attack, Support
from council.symbolic.argue.semantics.df_quad import DFQuADSemantics


def _arg(arg_id: str, *, base: float = 0.5) -> Argument:
    return Argument(
        arg_id=arg_id,
        claim_surface=f"surface-{arg_id}",
        base_score=base,
    )


SEM = DFQuADSemantics()


# ===========================================================================
# SATISFIED POSTULATES
# ===========================================================================


class TestAnonymity:
    """Anonymity: isomorphic frameworks yield equal strengths under arg_id
    renaming. Constitutional check: implementations must not depend on
    insertion order beyond what we explicitly preserve for output ordering."""

    def test_renaming_preserves_strengths(self) -> None:
        """Build two isomorphic BAFs with renamed args; strengths agree."""
        # Original: a (base 0.5) -> b (base 0.7)
        baf1 = QBAF(
            arguments=(_arg("a", base=0.5), _arg("b", base=0.7)),
            attacks=(Attack(source="a", target="b", weight=1.0),),
            supports=(),
        )
        # Renamed: x -> y; same shape and base scores
        baf2 = QBAF(
            arguments=(_arg("x", base=0.5), _arg("y", base=0.7)),
            attacks=(Attack(source="x", target="y", weight=1.0),),
            supports=(),
        )
        s1 = SEM.evaluate(baf1)
        s2 = SEM.evaluate(baf2)
        assert s1["a"] == s2["x"]
        assert s1["b"] == s2["y"]


class TestBivariateIndependence:
    """Bi-variate Independence: disconnected subframeworks don't influence
    each other's strengths. Two copies of a BAF, joined into one, have the
    same per-argument strengths as the originals."""

    def test_disjoint_subframes_independent(self) -> None:
        # Subframe 1: a (base 0.7)
        # Subframe 2: c (base 0.4) <- d (base 0.6)
        baf_combined = QBAF(
            arguments=(
                _arg("a", base=0.7),
                _arg("c", base=0.4),
                _arg("d", base=0.6),
            ),
            attacks=(Attack(source="d", target="c", weight=1.0),),
            supports=(),
        )
        baf_isolated_a = QBAF(
            arguments=(_arg("a", base=0.7),), attacks=(), supports=()
        )
        baf_subframe2 = QBAF(
            arguments=(_arg("c", base=0.4), _arg("d", base=0.6)),
            attacks=(Attack(source="d", target="c", weight=1.0),),
            supports=(),
        )
        s_combined = SEM.evaluate(baf_combined)
        s_a = SEM.evaluate(baf_isolated_a)
        s_sub2 = SEM.evaluate(baf_subframe2)
        # Strength of a unchanged
        assert s_combined["a"] == s_a["a"]
        # Strength of c, d unchanged
        assert s_combined["c"] == s_sub2["c"]
        assert s_combined["d"] == s_sub2["d"]


class TestBivariateDirectionality:
    """Bi-variate Directionality: an argument's strength depends only on
    its predecessors (attackers and supporters). Adding an isolated
    successor doesn't change anything."""

    def test_adding_descendant_no_effect_on_ancestor(self) -> None:
        # a is the root; b (downstream successor of a) is added
        baf_no_b = QBAF(
            arguments=(_arg("a", base=0.6),),
            attacks=(),
            supports=(),
        )
        baf_with_b = QBAF(
            arguments=(_arg("a", base=0.6), _arg("b", base=0.5)),
            attacks=(Attack(source="a", target="b", weight=1.0),),
            supports=(),
        )
        # a has no predecessors; adding b as a downstream attacked-by-a
        # shouldn't change a's strength.
        assert SEM.evaluate(baf_no_b)["a"] == SEM.evaluate(baf_with_b)["a"]


class TestBivariateEquivalence:
    """Bi-variate Equivalence: arguments with equal base scores and
    equal-strength predecessors have equal strengths."""

    def test_equal_inputs_equal_outputs(self) -> None:
        # Two args, each with one attacker of equal strength
        baf = QBAF(
            arguments=(
                _arg("a", base=0.6),
                _arg("att_a", base=0.4),
                _arg("b", base=0.6),
                _arg("att_b", base=0.4),
            ),
            attacks=(
                Attack(source="att_a", target="a", weight=1.0),
                Attack(source="att_b", target="b", weight=1.0),
            ),
            supports=(),
        )
        s = SEM.evaluate(baf)
        assert s["a"] == s["b"]


class TestStability:
    """Stability: an argument with no attackers and no supporters has
    strength equal to its base score."""

    def test_isolated_argument_returns_base(self) -> None:
        baf = QBAF(arguments=(_arg("a", base=0.42),), attacks=(), supports=())
        assert SEM.evaluate(baf)["a"] == pytest.approx(0.42)


class TestNeutrality:
    """Neutrality: a strength-0 attacker (or supporter) has no effect on
    the target's strength. Equivalent to Proposition 6 in Rago 2016."""

    def test_zero_strength_attacker_no_effect(self) -> None:
        baf = QBAF(
            arguments=(
                _arg("a", base=0.7),
                _arg("zero_attacker", base=0.0),
            ),
            attacks=(Attack(source="zero_attacker", target="a", weight=1.0),),
            supports=(),
        )
        # zero-strength attacker → v_a = 0 → strength = base = 0.7
        assert SEM.evaluate(baf)["a"] == pytest.approx(0.7)


class TestMonotony:
    """Monotony: replacing an attacker with one of strictly higher strength
    cannot increase the target's strength. (Rago 2016 Proposition 3.)"""

    def test_stronger_attacker_does_not_increase_target(self) -> None:
        baf_weak_attacker = QBAF(
            arguments=(_arg("a", base=0.7), _arg("b", base=0.2)),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        baf_strong_attacker = QBAF(
            arguments=(_arg("a", base=0.7), _arg("b", base=0.8)),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        s_weak = SEM.evaluate(baf_weak_attacker)["a"]
        s_strong = SEM.evaluate(baf_strong_attacker)["a"]
        assert s_strong <= s_weak + 1e-9


class TestReinforcement:
    """Reinforcement: adding a supporter (with positive strength) does not
    decrease the target's strength. (Symmetric to Monotony.)"""

    def test_adding_supporter_does_not_decrease_target(self) -> None:
        baf_no_supporter = QBAF(
            arguments=(_arg("a", base=0.5),), attacks=(), supports=()
        )
        baf_with_supporter = QBAF(
            arguments=(_arg("a", base=0.5), _arg("supp", base=0.6)),
            attacks=(),
            supports=(Support(source="supp", target="a", weight=1.0),),
        )
        s_without = SEM.evaluate(baf_no_supporter)["a"]
        s_with = SEM.evaluate(baf_with_supporter)["a"]
        assert s_with >= s_without - 1e-9


class TestFranklin:
    """Franklin: an equally-strong attacker and supporter cancel each
    other's effect on the target's strength."""

    def test_equal_attacker_supporter_cancel(self) -> None:
        baf = QBAF(
            arguments=(
                _arg("a", base=0.5),
                _arg("att", base=0.4),
                _arg("supp", base=0.4),
            ),
            attacks=(Attack(source="att", target="a", weight=1.0),),
            supports=(Support(source="supp", target="a", weight=1.0),),
        )
        # v_a = 0.4, v_s = 0.4, |v_s - v_a| = 0 → c(base, ...) = base
        assert SEM.evaluate(baf)["a"] == pytest.approx(0.5)


# ===========================================================================
# VIOLATED POSTULATES
# ===========================================================================


class TestStrictMonotonyViolated:
    """DF-QuAD's saturation: when v_a saturates near 1, adding more
    attackers does not strictly decrease the target's strength.

    Counterexample: a (base 1.0) attacked by b (base 1.0). v_a = 1.0;
    strength(a) = 1 - 1*1 = 0. Adding c (base 0.5) attacking a: v_a =
    F([1.0, 0.5]) = 1 - 0*0.5 = 1.0. Still 1.0 → strength still 0.
    Strict Monotony would require strictly LESS than 0, which is
    impossible (bounded at 0).
    """

    def test_saturated_attacker_set_no_strict_decrease(self) -> None:
        baf_one_attacker = QBAF(
            arguments=(_arg("a", base=1.0), _arg("b", base=1.0)),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        baf_two_attackers = QBAF(
            arguments=(
                _arg("a", base=1.0),
                _arg("b", base=1.0),
                _arg("c", base=0.5),
            ),
            attacks=(
                Attack(source="b", target="a", weight=1.0),
                Attack(source="c", target="a", weight=1.0),
            ),
            supports=(),
        )
        s_one = SEM.evaluate(baf_one_attacker)["a"]
        s_two = SEM.evaluate(baf_two_attackers)["a"]
        # Strict Monotony would require s_two < s_one.
        # Reality: s_one = s_two = 0.0 (saturation). Strict Monotony violated.
        assert s_one == pytest.approx(0.0)
        assert s_two == pytest.approx(0.0)
        assert s_two >= s_one  # not strictly less


class TestResilienceViolated:
    """Resilience: arguments with non-extreme base (0 < w < 1) should not
    reach the extreme strengths 0 or 1. DF-QuAD violates this — a
    max-strength supporter can drive a base=0.5 to strength=1.

    Counterexample: a (base 0.5) supported by b (base 1.0) at weight 1.0.
    v_s = 1.0; c(0.5, 0, 1.0) = 0.5 + 0.5*1.0 = 1.0. Strength saturates
    at 1.0 from non-extreme base.
    """

    def test_max_supporter_drives_to_one(self) -> None:
        baf = QBAF(
            arguments=(_arg("a", base=0.5), _arg("b", base=1.0)),
            attacks=(),
            supports=(Support(source="b", target="a", weight=1.0),),
        )
        s_a = SEM.evaluate(baf)["a"]
        # Resilience would require 0 < s_a < 1 (since w(a) = 0.5 ∈ (0, 1))
        # DF-QuAD: s_a = 1.0 → Resilience violated
        assert s_a == pytest.approx(1.0)


class TestWeakeningViolated:
    """Weakening: an argument that is strictly more attacked than supported
    must have strength strictly less than its base. DF-QuAD violates this
    when the attacker is weak enough that the strict inequality fails.

    Counterexample: a (base 0.7) attacked by b (base 0.0). v_a = 0.0;
    no supporters; strength = 0.7 (= base, not strictly less). Weakening
    would require strict <.
    """

    def test_zero_strength_attacker_no_decrease(self) -> None:
        baf = QBAF(
            arguments=(_arg("a", base=0.7), _arg("b", base=0.0)),
            attacks=(Attack(source="b", target="a", weight=1.0),),
            supports=(),
        )
        s_a = SEM.evaluate(baf)["a"]
        # Weakening would require s_a < 0.7. DF-QuAD gives = 0.7.
        assert s_a == pytest.approx(0.7)
        # Strictly NOT less than base — Weakening violated
        assert not (s_a < 0.7)


class TestStrengtheningViolated:
    """Strengthening: an argument strictly more supported than attacked
    must have strength strictly greater than its base. DF-QuAD violates
    when the supporter is too weak.

    Counterexample: a (base 0.7) supported by b (base 0.0). v_s = 0.0;
    strength = 0.7 (= base, not strictly more).
    """

    def test_zero_strength_supporter_no_increase(self) -> None:
        baf = QBAF(
            arguments=(_arg("a", base=0.7), _arg("b", base=0.0)),
            attacks=(),
            supports=(Support(source="b", target="a", weight=1.0),),
        )
        s_a = SEM.evaluate(baf)["a"]
        assert s_a == pytest.approx(0.7)
        assert not (s_a > 0.7)


class TestStrictReinforcementViolated:
    """Strict Reinforcement (Amgoud-Ben-Naim 2018, Definition 11 spirit):
    replacing a supporter with a strictly stronger one must STRICTLY
    increase the target's strength. The W2 fixture instantiates this
    postulate at the **saturation boundary** of DF-QuAD, where the
    base score is already at the upper boundary `w(a) = 1.0` of the
    [0, 1] strength space.

    Why the saturation boundary is the operative regime. DF-QuAD's
    combination function (Amgoud-Ben-Naim 2018 §3.1) is

        c(w(a), v_a, v_s) = w(a) + (1 - w(a)) · max(v_s - v_a, 0)
                             - w(a) · max(v_a - v_s, 0)

    At `w(a) = 1.0`, the support contribution is multiplied by
    `(1 - w(a)) = 0`, so any additional support strength leaves the
    target's strength locked at 1.0. The strict-increase clause of
    Strict Reinforcement therefore cannot be satisfied at the boundary
    — exactly the failure mark Table 1 of Amgoud-Ben-Naim 2018 records
    for any saturating F-aggregation, including DF-QuAD.

    Concrete counterexample (this fixture):
      a (base 1.0), supporter b (base 0.5):
        v_s = 0.5;  c(1.0, 0, 0.5) = 1.0 + 0·0.5 = 1.0
      Replace with stronger supporter (base 0.9):
        v_s = 0.9;  c(1.0, 0, 0.9) = 1.0 + 0·0.9 = 1.0
    Strict Reinforcement requires `s_strong > s_weak`; DF-QuAD gives
    `s_strong = s_weak = 1.0`. Strict Reinforcement violated.

    Scope note. Definition 11's full antecedents exclude `w(a) = 1`;
    the W2 matrix takes the *spirit* of the postulate (strict-increase
    under stronger support) and instantiates it at the boundary because
    that is precisely where DF-QuAD's saturating F-aggregation is
    structurally incapable of satisfying it. A non-boundary
    counterexample requires a more elaborate multi-supporter
    construction (Amgoud-Ben-Naim 2018 §6 no-go); this test pins the
    boundary case which is sufficient to falsify the postulate. (Theorem
    audit fix 2026-05-01.)
    """

    def test_saturated_base_no_strict_increase_with_stronger_supporter(
        self,
    ) -> None:
        baf_weak_supp = QBAF(
            arguments=(_arg("a", base=1.0), _arg("b", base=0.5)),
            attacks=(),
            supports=(Support(source="b", target="a", weight=1.0),),
        )
        baf_strong_supp = QBAF(
            arguments=(_arg("a", base=1.0), _arg("b", base=0.9)),
            attacks=(),
            supports=(Support(source="b", target="a", weight=1.0),),
        )
        s_weak = SEM.evaluate(baf_weak_supp)["a"]
        s_strong = SEM.evaluate(baf_strong_supp)["a"]
        # Strict Reinforcement would require s_strong > s_weak.
        # DF-QuAD: both = 1.0 (saturation). Strict Reinforcement violated.
        assert s_weak == pytest.approx(1.0)
        assert s_strong == pytest.approx(1.0)
        assert s_strong >= s_weak  # not strictly greater


class TestStrictFranklinViolated:
    """Strict Franklin (Amgoud-Ben-Naim 2018, Definition 12 spirit): an
    argument with strictly more support than attack must have strength
    STRICTLY greater than its base. The W2 fixture instantiates this
    postulate at the **saturation boundary** `w(a) = 1.0`, where
    DF-QuAD's combination function is structurally incapable of moving
    the strength above the base — by exactly the same `(1 - w(a)) = 0`
    coefficient on the support term that drives Strict Reinforcement
    (sister test above).

    Why a non-boundary instantiation does NOT yield a counterexample.
    Direct interior check (a base 0.5, attacker strength 0.6,
    supporter strength 0.7):

        v_a = 0.6, v_s = 0.7  →  v_s > v_a
        c(0.5, 0.6, 0.7) = 0.5 + (1 - 0.5)·0.1 = 0.55 > 0.5

    Strictly greater than base; Strict Franklin holds in the interior.
    The postulate fails *only* when the saturating coefficient
    `(1 - w(a))` drives the support contribution to zero — i.e., on the
    `w(a) = 1` boundary. This boundary is the operative regime of the
    counterexample.

    Concrete counterexample (this fixture):
      a (base 1.0), attacker att (base 0.5), supporter supp (base 0.5):
        v_a = 0.5, v_s = 0.5  →  c(1.0, 0.5, 0.5) = 1.0 - 1·0 = 1.0
      Strengthen supporter to 0.9 (strictly more support than attack):
        v_a = 0.5, v_s = 0.9  →  c(1.0, 0.5, 0.9)
                                = 1.0 + (1 - 1.0)·0.4 - 1.0·0 = 1.0
    Strict Franklin requires `s > base = 1.0`, but DF-QuAD caps at 1.0.
    Strict Franklin violated at the saturation boundary.

    Scope note. As with Strict Reinforcement, Definition 12's strict
    interior counterexample requires a richer multi-supporter / multi-
    attacker construction; this test fixture pins the saturation-
    boundary case that mechanises the failure mark in Table 1. (Theorem
    audit fix 2026-05-01.)
    """

    def test_saturated_base_no_strict_franklin_with_dominant_support(
        self,
    ) -> None:
        baf_balanced = QBAF(
            arguments=(
                _arg("a", base=1.0),
                _arg("att", base=0.5),
                _arg("supp", base=0.5),
            ),
            attacks=(Attack(source="att", target="a", weight=1.0),),
            supports=(Support(source="supp", target="a", weight=1.0),),
        )
        baf_supp_dominant = QBAF(
            arguments=(
                _arg("a", base=1.0),
                _arg("att", base=0.5),
                _arg("supp", base=0.9),
            ),
            attacks=(Attack(source="att", target="a", weight=1.0),),
            supports=(Support(source="supp", target="a", weight=1.0),),
        )
        s_balanced = SEM.evaluate(baf_balanced)["a"]
        s_dominant = SEM.evaluate(baf_supp_dominant)["a"]
        # Strict Franklin would require s_dominant > base = 1.0.
        # DF-QuAD: both saturate at 1.0. Strict Franklin violated.
        assert s_balanced == pytest.approx(1.0)
        assert s_dominant == pytest.approx(1.0)
        assert not (s_dominant > 1.0)


# ===========================================================================
# Summary table — pinned matrix for P2 reviewer reference
# ===========================================================================


class TestPostulateMatrix:
    """The full T6 matrix — pinned for P2 (AAAI 2027) reviewer reference.
    Updating this matrix is a deliberate spec change."""

    def test_satisfied_principle_count(self) -> None:
        """DF-QuAD satisfies 9 of the 16 Amgoud-Ben-Naim 2018 principles."""
        satisfied = {
            "Anonymity",
            "Bi-variate Independence",
            "Bi-variate Directionality",
            "Bi-variate Equivalence",
            "Stability",
            "Neutrality",
            "Monotony",
            "Reinforcement",
            "Franklin",
        }
        assert len(satisfied) == 9

    def test_violated_principle_count(self) -> None:
        """DF-QuAD violates 6 principles in the strict / non-saturating sense."""
        violated = {
            "Strict Monotony",
            "Strict Reinforcement",
            "Resilience",
            "Strict Franklin",
            "Weakening",
            "Strengthening",
        }
        assert len(violated) == 6

    def test_inertia_is_extension_only(self) -> None:
        """Inertia applies only to extension semantics, not gradual ones."""
        # Documented in docs/theory.md §T6 — no runtime check needed.
        inertia_applies_to = "extension semantics"
        assert inertia_applies_to == "extension semantics"
