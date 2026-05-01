"""Integration: cgs_to_ispl output is parseable by MCMAS v1.3.0.

Stage 3 / Slice 3.2 of the T7 ATLK revision (specs/t7-atlk-revision.md).

This test invokes the real ``mcmas`` binary on the canonical T_3 ISPL.
Gated by ``@pytest.mark.integration`` and ``RUN_INTEGRATION=1``. The
parse-success here is the load-bearing precondition for Stage 5's
formula-evaluation tests — if MCMAS can't parse our output, no
verification is possible.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from council.symbolic.verify.cgs import canonical_t3_cgs, cgs_to_ispl
from council.symbolic.verify.ltlf import Atom, CoalitionFinally, Knows

pytestmark = pytest.mark.integration


def _require_run_integration() -> None:
    if os.environ.get("RUN_INTEGRATION") != "1":
        pytest.skip("set RUN_INTEGRATION=1 to enable the MCMAS subprocess")


def _require_mcmas() -> str:
    path = shutil.which("mcmas")
    if path is None:
        pytest.skip("mcmas binary not on PATH")
    return path


def _run_mcmas(ispl_text: str, *, atlk: int | None = 2) -> subprocess.CompletedProcess[str]:
    mcmas_bin = _require_mcmas()
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".ispl", delete=False
    ) as tmp:
        tmp.write(ispl_text)
        path = tmp.name
    try:
        cmd = [mcmas_bin]
        if atlk is not None:
            cmd.extend(["-atlk", str(atlk)])
        cmd.append(path)
        return subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        Path(path).unlink(missing_ok=True)


class TestMCMASParseSuccess:
    """The ISPL emitted from canonical_t3_cgs parses without error."""

    def test_canonical_t3_default_parses(self) -> None:
        _require_run_integration()
        cgs = canonical_t3_cgs()
        ispl = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        result = _run_mcmas(ispl)
        assert "parsed successfully" in result.stdout, (
            f"MCMAS did not parse the ISPL.\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}\n"
            f"--- ISPL (first 2000 chars) ---\n{ispl[:2000]}"
        )

    def test_canonical_t3_with_witness_parses(self) -> None:
        _require_run_integration()
        cgs = canonical_t3_cgs(witness_initial={"agent_alice": True})
        ispl = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        result = _run_mcmas(ispl)
        assert "parsed successfully" in result.stdout

    def test_atlk_formula_parses_under_semantics_2(self) -> None:
        _require_run_integration()
        cgs = canonical_t3_cgs()
        # The headline T7 formula: <g_alice> F K(agent_alice, evidence_p1_alice)
        formula = CoalitionFinally(
            group="g_alice",
            arg=Knows(agent="agent_alice", arg=Atom("evidence_p1_alice")),
        )
        ispl = cgs_to_ispl(cgs, [formula])
        result = _run_mcmas(ispl, atlk=2)
        assert "parsed successfully" in result.stdout, (
            f"MCMAS did not parse the ATLK formula.\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}\n"
        )

    def test_max_rounds_3_parses(self) -> None:
        # State-explosion sanity check: confirm max_rounds=3 still parses.
        _require_run_integration()
        cgs = canonical_t3_cgs(max_rounds=3)
        ispl = cgs_to_ispl(cgs, [Atom("consensus_p1")])
        result = _run_mcmas(ispl)
        assert "parsed successfully" in result.stdout
