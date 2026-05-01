"""Integration: the T7 ATLK headline theorem on the canonical T_3 CGS.

Stage 5 / Slice 5.3 of the T7 ATLK revision (specs/t7-atlk-revision.md).
The load-bearing test — invokes the real ``mcmas`` v1.3.0 binary on
the ATLK formula
    ⟨⟨{i}⟩⟩ F K_i evidence(p1, i)
under ``-atlk 2`` (per ADR-0021), once per agent, and asserts the
verdicts match the spec's mathematical statement of T7.

Specifically:
  - **Negative (T7 no-go).** On the canonical T_3 instance (no agent
    starts with witness), Strategically-Witnessable(q_T3) = ∅. Every
    per-agent formula evaluates FALSE.
  - **Positive (sanity).** On the alice-witness instance, the formula
    is TRUE for alice and FALSE for bob and carol. Strategically-
    Witnessable = {p1}.
  - **Reachability sanity (CTL).** EF disclosed_p1_alice is FALSE on
    T_3 (no path leads to disclosure) and TRUE on the alice-witness
    instance (alice can choose propose_with_witness in round 0). This
    cross-checks the encoding's evolution rules independent of the
    ATL operator.

Gated by ``@pytest.mark.integration`` and ``RUN_INTEGRATION=1``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from council.symbolic.verify.atl_witness import (
    evidence_backed_arg_ids_via_atl,
    parse_mcmas_verdicts,
)
from council.symbolic.verify.cgs import canonical_t3_cgs, cgs_to_ispl
from council.symbolic.verify.ltlf import Atom, Finally

pytestmark = pytest.mark.integration


def _require_run_integration() -> None:
    if os.environ.get("RUN_INTEGRATION") != "1":
        pytest.skip("set RUN_INTEGRATION=1 to enable the MCMAS subprocess")


def _require_mcmas() -> str:
    path = shutil.which("mcmas")
    if path is None:
        pytest.skip("mcmas binary not on PATH")
    return path


def _mcmas_runner(ispl: str, *, atlk: int, ufgroup: str | None = None) -> str:
    """Real subprocess MCMAS runner used by Slice 5.3 integration tests.

    Writes ``ispl`` to a temp file, invokes ``mcmas -atlk <atlk>
    [-ufgroup <name>] <file>``, captures stdout, returns it. Per
    ADR-0021, ``ufgroup`` scopes uniform-strategy generation to the
    named coalition only (matching the AHK 2002 ATL semantics for
    singleton-coalition formulas).
    """
    mcmas_bin = _require_mcmas()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ispl", delete=False) as tmp:
        tmp.write(ispl)
        path = tmp.name
    try:
        cmd = [mcmas_bin, "-atlk", str(atlk)]
        if ufgroup is not None:
            cmd.extend(["-ufgroup", ufgroup])
        cmd.append(path)
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        return result.stdout
    finally:
        Path(path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Headline theorem: T7 ATLK under -atlk 2
# ---------------------------------------------------------------------------


class TestT7HeadlineNoGo:
    """The T7 negative claim: on the canonical T_3 instance, no agent
    has a uniform strategy to come to know evidence for p1.
    """

    def test_strategically_witnessable_empty_on_t3(self) -> None:
        _require_run_integration()
        cgs = canonical_t3_cgs()
        result = evidence_backed_arg_ids_via_atl(
            cgs, ["p1"], runner=_mcmas_runner
        )
        # The headline T7 result: no arg_id is strategically witnessable.
        assert result == frozenset(), (
            f"Expected Strategically-Witnessable(q_T3) = ∅ but got {result!r}.\n"
            f"This would indicate either an encoding bug (CGS doesn't match\n"
            f"the spec's M(P, Π, Θ, R)) or a verdict-parser bug."
        )


class TestT7HeadlinePositive:
    """The T7 positive sanity: when alice starts with witness, alice has
    a uniform strategy to come to know evidence; bob and carol do not.
    """

    def test_alice_witness_makes_p1_strategically_witnessable(self) -> None:
        # Positive instance uses max_rounds=1 to keep MCMAS strategy
        # enumeration tractable. Per ADR-0020 §"max_rounds" and the
        # Stage 5 Slice 5.3 finding: -atlk 2 strategy enumeration is
        # PSPACE-hard; max_rounds=2 with alice's strategy space takes
        # > 180s, while max_rounds=1 + -ufgroup completes in ~60s. The
        # headline NEGATIVE theorem uses max_rounds=2 (it converges
        # fast because the verdict is FALSE).
        _require_run_integration()
        cgs = canonical_t3_cgs(
            max_rounds=1, witness_initial={"agent_alice": True}
        )
        result = evidence_backed_arg_ids_via_atl(
            cgs, ["p1"], runner=_mcmas_runner
        )
        # The T7 corollary: with at least one agent's witness, p1 is
        # strategically witnessable.
        assert result == frozenset({"p1"})


class TestT7VerdictMatrix:
    """Per-agent verdict breakdown on the alice-witness positive instance.

    Confirms the AT-LEAST-ONE quantifier in Strategically-Witnessable's
    definition is doing the right thing: only alice's formula is TRUE;
    bob's and carol's are FALSE; alice alone makes p1 witnessable.
    """

    def test_per_agent_verdicts_alice_witness(self) -> None:
        # Same scope reduction as test_alice_witness_makes_p1...:
        # max_rounds=1 to keep -atlk 2 strategy enumeration tractable.
        _require_run_integration()
        cgs = canonical_t3_cgs(
            max_rounds=1, witness_initial={"agent_alice": True}
        )
        # Per ADR-0021, each agent's coalition formula must be checked
        # under -ufgroup g_<short> so the AHK 2002 semantics holds. So
        # one MCMAS call per agent.
        from council.symbolic.verify.atl_witness import _build_witness_formula

        per_agent: dict[str, bool] = {}
        for agent in cgs.agents:
            short = agent.agent_id.removeprefix("agent_")
            formula = _build_witness_formula("p1", agent.agent_id)
            ispl = cgs_to_ispl(cgs, [formula])
            stdout = _mcmas_runner(ispl, atlk=2, ufgroup=f"g_{short}")
            verdicts = parse_mcmas_verdicts(stdout)
            assert len(verdicts) == 1
            per_agent[short] = verdicts[0]
        assert per_agent == {"alice": True, "bob": False, "carol": False}, (
            f"Expected only alice's formula to be TRUE; got {per_agent!r}"
        )


# ---------------------------------------------------------------------------
# Encoding-faithfulness sanity (CTL reachability cross-check)
# ---------------------------------------------------------------------------


class TestEncodingReachabilitySanity:
    """Cross-check the encoding's evolution rules with plain-CTL reachability.

    These tests do not use ATL operators — they check pure reachability
    on the underlying transition system. If the verdicts match the
    expected behaviour of canonical_t3_cgs.step (i.e., propose_with_witness
    only enabled when has_witness=true), the ISPL evolution rules are
    consistent with the Python-side step simulator.
    """

    def test_no_disclosure_reachable_on_t3(self) -> None:
        _require_run_integration()
        cgs = canonical_t3_cgs()
        # EF evidence_p1_alice — is there ANY path where alice discloses?
        # On T_3, no — alice's protocol disables propose_with_witness.
        formula = Finally(arg=Atom("evidence_p1_alice"))
        ispl = cgs_to_ispl(cgs, [formula])
        stdout = _mcmas_runner(ispl, atlk=2)
        verdicts = parse_mcmas_verdicts(stdout)
        assert verdicts == [False], (
            f"Expected EF evidence_p1_alice = FALSE on T_3 (alice cannot disclose) "
            f"but got {verdicts!r}"
        )

    def test_disclosure_reachable_when_alice_has_witness(self) -> None:
        _require_run_integration()
        cgs = canonical_t3_cgs(witness_initial={"agent_alice": True})
        formula = Finally(arg=Atom("evidence_p1_alice"))
        ispl = cgs_to_ispl(cgs, [formula])
        stdout = _mcmas_runner(ispl, atlk=2)
        verdicts = parse_mcmas_verdicts(stdout)
        assert verdicts == [True], (
            f"Expected EF evidence_p1_alice = TRUE on alice-witness instance "
            f"(alice can choose propose_with_witness) but got {verdicts!r}"
        )

    def test_consensus_reachable(self) -> None:
        _require_run_integration()
        cgs = canonical_t3_cgs(max_rounds=3)
        # Sanity: the CGS does support reaching consensus (all three vote).
        formula = Finally(arg=Atom("consensus_p1"))
        ispl = cgs_to_ispl(cgs, [formula])
        stdout = _mcmas_runner(ispl, atlk=2)
        verdicts = parse_mcmas_verdicts(stdout)
        assert verdicts == [True], (
            f"Expected EF consensus_p1 = TRUE (CGS supports reaching consensus) "
            f"but got {verdicts!r}"
        )
