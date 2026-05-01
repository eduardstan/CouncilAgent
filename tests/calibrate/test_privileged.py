"""Tests for council.calibrate.privileged — PrivilegedKnowledgeCalibrator.

Pins the calibrator to Anonymous 2026 *Masked by Consensus: Disentangling
Privileged Knowledge in LLM Correctness* (OpenReview du3ZBA8Z3Z), under
``papers/2 --- calibration and disagreement/``. Paper §4.3 finds:

  - factual tasks have ~5% premium gap on disagreement subsets
    (statistically significant across Mintaka, TriviaQA, HotPotQA)
  - mathematical reasoning has no premium gap (paper Figure 3 right panel)
  - coding is unmeasured by the paper; ``COUNCILAGENT_NS_MASTER_PLAN.md``
    line 768 says "partial"; we interpolate to 2.5%

The calibrator's mixing model self_weight * raw + peer_weight * peer
is documented in ADR-0017 (next slice).
"""

from __future__ import annotations

import pytest

from council.calibrate import Calibrator
from council.calibrate.privileged import (
    DEFAULT_DOMAIN_GAPS,
    DomainGap,
    PrivilegedKnowledgeCalibrator,
)
from council.dialect.moves import ClaimDomain


class TestDomainGap:
    """The DomainGap value object encodes the self/peer weight derivation."""

    def test_self_weight_and_peer_weight_sum_to_one(self) -> None:
        for gap in (0.0, 0.05, 0.5, 1.0):
            dg = DomainGap(gap)
            assert dg.self_weight + dg.peer_weight == pytest.approx(1.0, abs=1e-12)

    def test_zero_gap_yields_balanced_weights(self) -> None:
        dg = DomainGap(0.0)
        assert dg.self_weight == pytest.approx(0.5)
        assert dg.peer_weight == pytest.approx(0.5)

    def test_five_percent_gap_matches_paper(self) -> None:
        # Paper §4.3 ~5% premium gap on factual tasks.
        dg = DomainGap(0.05)
        assert dg.self_weight == pytest.approx(0.525)
        assert dg.peer_weight == pytest.approx(0.475)

    def test_full_gap_yields_max_self_trust(self) -> None:
        dg = DomainGap(1.0)
        assert dg.self_weight == pytest.approx(1.0)
        assert dg.peer_weight == pytest.approx(0.0)

    def test_negative_gap_raises(self) -> None:
        with pytest.raises(ValueError, match="gap"):
            DomainGap(-0.01)

    def test_gap_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="gap"):
            DomainGap(1.01)


class TestDefaultDomainGaps:
    """Defaults must cover every ClaimDomain member with paper-grounded values."""

    def test_covers_all_claim_domains(self) -> None:
        for domain in ClaimDomain:
            assert domain in DEFAULT_DOMAIN_GAPS, f"missing default for {domain}"

    def test_factual_default_is_five_percent_gap(self) -> None:
        # Anonymous 2026 §4.3 Figure 3: ~5% factual premium gap.
        assert DEFAULT_DOMAIN_GAPS[ClaimDomain.FREE].gap == pytest.approx(0.05)

    def test_math_default_is_zero_gap(self) -> None:
        # Anonymous 2026 §4.3 Figure 3: no premium gap on math.
        assert DEFAULT_DOMAIN_GAPS[ClaimDomain.ARITH].gap == pytest.approx(0.0)

    def test_coding_default_is_partial(self) -> None:
        # Master plan "coding partial"; interpolation between FREE and ARITH.
        assert 0.0 < DEFAULT_DOMAIN_GAPS[ClaimDomain.CODE].gap < 0.05

    def test_formal_domains_match_math(self) -> None:
        # FOL and LTLF are formal/symbolic — same family as ARITH.
        assert DEFAULT_DOMAIN_GAPS[ClaimDomain.FOL].gap == pytest.approx(0.0)
        assert DEFAULT_DOMAIN_GAPS[ClaimDomain.LTLF].gap == pytest.approx(0.0)


class TestPrivilegedKnowledgeCalibratorContract:
    """ABC compliance + the safe-fallback unknown-agent contract."""

    def test_implements_calibrator_abc(self) -> None:
        cal = PrivilegedKnowledgeCalibrator(peer_consensus={"A": 0.5})
        assert isinstance(cal, Calibrator)

    def test_unknown_agent_id_returns_raw_unchanged(self) -> None:
        # Safe fallback: caller passed an agent we have no peer info for.
        cal = PrivilegedKnowledgeCalibrator(peer_consensus={"A": 0.4})
        assert cal.calibrate(0.7, "stranger", ClaimDomain.FREE) == pytest.approx(0.7)


class TestPrivilegedKnowledgeMixing:
    """Self/peer mixing under the default domain-gap weights."""

    def test_math_uses_balanced_self_peer_mix(self) -> None:
        # gap=0 → self_weight=peer_weight=0.5 → output = (raw + peer) / 2.
        cal = PrivilegedKnowledgeCalibrator(peer_consensus={"A": 0.4})
        assert cal.calibrate(0.8, "A", ClaimDomain.ARITH) == pytest.approx(0.6)

    def test_factual_biases_toward_self(self) -> None:
        # gap=0.05 → 0.525 * raw + 0.475 * peer.
        cal = PrivilegedKnowledgeCalibrator(peer_consensus={"A": 0.4})
        expected = 0.525 * 0.8 + 0.475 * 0.4
        assert cal.calibrate(0.8, "A", ClaimDomain.FREE) == pytest.approx(expected)

    def test_domain_dispatch_changes_output(self) -> None:
        # Same (raw, peer) yields different calibrated values for FREE vs ARITH
        # because the default gaps differ.
        cal = PrivilegedKnowledgeCalibrator(peer_consensus={"A": 0.3})
        free_value = cal.calibrate(0.9, "A", ClaimDomain.FREE)
        math_value = cal.calibrate(0.9, "A", ClaimDomain.ARITH)
        assert free_value != math_value
        # FREE biases toward raw (higher than the unweighted mean) when raw > peer.
        assert free_value > math_value

    def test_self_equals_peer_yields_self_unchanged(self) -> None:
        # When raw == peer, the convex combination is the identity for any gap.
        cal = PrivilegedKnowledgeCalibrator(peer_consensus={"A": 0.6})
        for domain in ClaimDomain:
            assert cal.calibrate(0.6, "A", domain) == pytest.approx(0.6)

    def test_linear_in_raw_with_self_weight_slope(self) -> None:
        # Holding peer fixed, calibrate is linear in raw with slope = self_weight.
        peer = 0.3
        cal = PrivilegedKnowledgeCalibrator(peer_consensus={"A": peer})
        gap = DEFAULT_DOMAIN_GAPS[ClaimDomain.FREE]
        v_low = cal.calibrate(0.2, "A", ClaimDomain.FREE)
        v_high = cal.calibrate(0.8, "A", ClaimDomain.FREE)
        slope = (v_high - v_low) / (0.8 - 0.2)
        assert slope == pytest.approx(gap.self_weight, abs=1e-12)


class TestPrivilegedKnowledgeCustomGaps:
    """User-supplied domain_gaps must override defaults."""

    def test_custom_gaps_override_defaults(self) -> None:
        # Override FREE with gap=0 (force balanced); rest fall back to defaults.
        custom = {**DEFAULT_DOMAIN_GAPS, ClaimDomain.FREE: DomainGap(0.0)}
        cal = PrivilegedKnowledgeCalibrator(
            peer_consensus={"A": 0.4},
            domain_gaps=custom,
        )
        # Now FREE behaves like ARITH (balanced mixing).
        free_value = cal.calibrate(0.8, "A", ClaimDomain.FREE)
        math_value = cal.calibrate(0.8, "A", ClaimDomain.ARITH)
        assert free_value == pytest.approx(math_value)


class TestPrivilegedKnowledgeBoundaries:
    """Clamping + determinism."""

    def test_clamps_above_one(self) -> None:
        # Malformed inputs (e.g., raw=1.5) should not yield > 1.
        cal = PrivilegedKnowledgeCalibrator(peer_consensus={"A": 1.5})
        assert cal.calibrate(1.5, "A", ClaimDomain.FREE) == pytest.approx(1.0)

    def test_clamps_below_zero(self) -> None:
        cal = PrivilegedKnowledgeCalibrator(peer_consensus={"A": -0.5})
        assert cal.calibrate(-0.5, "A", ClaimDomain.ARITH) == pytest.approx(0.0)

    def test_deterministic_across_repeated_calls(self) -> None:
        cal = PrivilegedKnowledgeCalibrator(peer_consensus={"A": 0.4})
        first = cal.calibrate(0.7, "A", ClaimDomain.FREE)
        for _ in range(99):
            assert cal.calibrate(0.7, "A", ClaimDomain.FREE) == first
