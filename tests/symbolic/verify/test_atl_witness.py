"""Tests for council.symbolic.verify.atl_witness — ATLK headline-theorem witness.

Stage 5 / Slice 5.1 of the T7 ATLK revision (specs/t7-atlk-revision.md).
Pure unit tests with a stubbed MCMAS runner. The real subprocess is
exercised in tests/integration/test_t7_atlk.py (Slice 5.3).
"""

from __future__ import annotations

import pytest

from council.symbolic.verify.atl_witness import (
    MCMASRunner,
    evidence_backed_arg_ids_via_atl,
    parse_mcmas_verdicts,
)
from council.symbolic.verify.cgs import canonical_t3_cgs

# ---------------------------------------------------------------------------
# parse_mcmas_verdicts — pure function over MCMAS stdout
# ---------------------------------------------------------------------------


class TestParseMCMASVerdicts:
    """Extract ordered list[bool] from MCMAS stdout per the v1.3.0 format."""

    def test_single_true_verdict(self) -> None:
        stdout = "  Formula number 1: (consensus_p1), is TRUE in the model\n"
        assert parse_mcmas_verdicts(stdout) == [True]

    def test_single_false_verdict(self) -> None:
        stdout = "  Formula number 1: (<g_alice> F evidence_p1_alice), is FALSE in the model\n"
        assert parse_mcmas_verdicts(stdout) == [False]

    def test_multiple_verdicts_in_order(self) -> None:
        stdout = (
            "  Formula number 1: (X), is TRUE in the model\n"
            "  Formula number 2: (Y), is FALSE in the model\n"
            "  Formula number 3: (Z), is TRUE in the model\n"
        )
        assert parse_mcmas_verdicts(stdout) == [True, False, True]

    def test_real_mcmas_smoke_output(self) -> None:
        # Reproduces the actual smoke-test output from the Stage 1 ATL probe.
        stdout = (
            "Verifying properties...\n"
            "  Formula number 1: (<alice_only>F alice_flag), is TRUE in the model\n"
            "  Formula number 2: (! (<alice_only>F bob_flag)), is TRUE in the model\n"
            "  Formula number 3: (<both>F both_flags), is TRUE in the model\n"
            "  Formula number 4: (EF both_flags), is TRUE in the model\n"
            "done, 4 formulae successfully read and checked\n"
        )
        assert parse_mcmas_verdicts(stdout) == [True, True, True, True]

    def test_empty_stdout_raises(self) -> None:
        with pytest.raises(ValueError, match=r"no verdicts"):
            parse_mcmas_verdicts("")

    def test_stdout_without_verdict_lines_raises(self) -> None:
        stdout = "Loaded model.\nDone.\n"
        with pytest.raises(ValueError, match=r"no verdicts"):
            parse_mcmas_verdicts(stdout)

    def test_malformed_verdict_word_raises(self) -> None:
        # A "Formula number 1:" line without a TRUE/FALSE outcome is
        # malformed; we should not silently ignore it.
        stdout = "  Formula number 1: (X), is MAYBE in the model\n"
        with pytest.raises(ValueError, match=r"no verdicts"):
            parse_mcmas_verdicts(stdout)


# ---------------------------------------------------------------------------
# evidence_backed_arg_ids_via_atl — composition with a stub runner
# ---------------------------------------------------------------------------


class _FakeMCMASRunner:
    """Stub runner that returns canned stdout per call.

    Records every (ispl, atlk) call so tests can assert the right
    formulas were sent.
    """

    def __init__(self, canned_stdout: str) -> None:
        self._canned = canned_stdout
        self.calls: list[tuple[str, int]] = []

    def __call__(self, ispl: str, *, atlk: int) -> str:
        self.calls.append((ispl, atlk))
        return self._canned


class TestEvidenceBackedArgIdsViaATL:
    """Composition: build formulas, call runner, parse verdicts, return arg ids."""

    def test_returns_frozenset_when_no_witness(self) -> None:
        # T_3 instance: every per-agent formula evaluates FALSE → empty set.
        runner = _FakeMCMASRunner(
            canned_stdout=(
                "  Formula number 1: (<g_alice> F K(agent_alice, evidence_p1_alice)), is FALSE in the model\n"
                "  Formula number 2: (<g_bob> F K(agent_bob, evidence_p1_bob)), is FALSE in the model\n"
                "  Formula number 3: (<g_carol> F K(agent_carol, evidence_p1_carol)), is FALSE in the model\n"
            )
        )
        cgs = canonical_t3_cgs()
        result = evidence_backed_arg_ids_via_atl(cgs, ["p1"], runner=runner)
        assert isinstance(result, frozenset)
        assert result == frozenset()

    def test_returns_p1_when_alice_has_witness(self) -> None:
        # Positive instance: alice's formula TRUE, others FALSE → {p1}.
        runner = _FakeMCMASRunner(
            canned_stdout=(
                "  Formula number 1: (<g_alice> F K(agent_alice, evidence_p1_alice)), is TRUE in the model\n"
                "  Formula number 2: (<g_bob> F K(agent_bob, evidence_p1_bob)), is FALSE in the model\n"
                "  Formula number 3: (<g_carol> F K(agent_carol, evidence_p1_carol)), is FALSE in the model\n"
            )
        )
        cgs = canonical_t3_cgs(witness_initial={"agent_alice": True})
        result = evidence_backed_arg_ids_via_atl(cgs, ["p1"], runner=runner)
        assert result == frozenset({"p1"})

    def test_runner_invoked_with_atlk_2(self) -> None:
        # ADR-0021 locks `-atlk 2` as the operative semantics.
        runner = _FakeMCMASRunner(
            canned_stdout=(
                "  Formula number 1: (X), is FALSE in the model\n"
                "  Formula number 2: (X), is FALSE in the model\n"
                "  Formula number 3: (X), is FALSE in the model\n"
            )
        )
        cgs = canonical_t3_cgs()
        evidence_backed_arg_ids_via_atl(cgs, ["p1"], runner=runner)
        assert len(runner.calls) == 1
        _, atlk = runner.calls[0]
        assert atlk == 2

    def test_runner_invoked_with_ispl_containing_headline_formulas(self) -> None:
        # The ISPL passed to MCMAS must include the per-agent ATLK formulas.
        runner = _FakeMCMASRunner(
            canned_stdout=(
                "  Formula number 1: (X), is FALSE in the model\n"
                "  Formula number 2: (X), is FALSE in the model\n"
                "  Formula number 3: (X), is FALSE in the model\n"
            )
        )
        cgs = canonical_t3_cgs()
        evidence_backed_arg_ids_via_atl(cgs, ["p1"], runner=runner)
        ispl, _ = runner.calls[0]
        # All three per-agent ATLK formulas must appear in the emitted ISPL.
        assert "<g_alice> F K(agent_alice, evidence_p1_alice)" in ispl
        assert "<g_bob> F K(agent_bob, evidence_p1_bob)" in ispl
        assert "<g_carol> F K(agent_carol, evidence_p1_carol)" in ispl

    def test_arg_id_included_iff_any_agent_has_strategy(self) -> None:
        # If only bob has a strategy for p1, p1 is still witnessable.
        runner = _FakeMCMASRunner(
            canned_stdout=(
                "  Formula number 1: (X), is FALSE in the model\n"
                "  Formula number 2: (X), is TRUE in the model\n"
                "  Formula number 3: (X), is FALSE in the model\n"
            )
        )
        cgs = canonical_t3_cgs(witness_initial={"agent_bob": True})
        result = evidence_backed_arg_ids_via_atl(cgs, ["p1"], runner=runner)
        assert result == frozenset({"p1"})

    def test_empty_arg_ids_returns_empty_set_without_runner_call(self) -> None:
        runner = _FakeMCMASRunner(canned_stdout="")
        cgs = canonical_t3_cgs()
        result = evidence_backed_arg_ids_via_atl(cgs, [], runner=runner)
        assert result == frozenset()
        # No MCMAS call should be made if there are no arg_ids to test.
        assert runner.calls == []

    def test_verdict_count_mismatch_raises(self) -> None:
        # Sent 3 formulas but got 2 verdicts back — encoding bug, must raise.
        runner = _FakeMCMASRunner(
            canned_stdout=(
                "  Formula number 1: (X), is FALSE in the model\n"
                "  Formula number 2: (X), is FALSE in the model\n"
            )
        )
        cgs = canonical_t3_cgs()
        with pytest.raises(ValueError, match=r"verdict count"):
            evidence_backed_arg_ids_via_atl(cgs, ["p1"], runner=runner)


# ---------------------------------------------------------------------------
# MCMASRunner Protocol contract
# ---------------------------------------------------------------------------


class TestMCMASRunnerProtocol:
    def test_fake_runner_satisfies_protocol(self) -> None:
        runner: MCMASRunner = _FakeMCMASRunner(canned_stdout="")
        # Smoke: the fake runner is a usable MCMASRunner. mypy enforces
        # the Protocol structurally; this is a runtime smoke test.
        assert callable(runner)
