"""W1 acceptance test (master plan §7): offline MCMAS check on a 4-agent /
4-round trace verifies EventuallyDecide and RefutationReachable.

Gated by RUN_INTEGRATION=1 AND `mcmas` available on PATH.

STATUS (2026-04-30): PASSING against MCMAS 1.3.0 — see
docs/adr/0005-mcmas-resolved.md. Install instructions in
docs/installation.md §"MCMAS — verified install". The ISPL emitter that
drives this test is verified at the structural level by 30 tests in
tests/symbolic/verify/test_ispl.py and end-to-end by this test against
the real MCMAS binary.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from council.dialect.moves import Challenge, Claim, Concede, Propose, Vote
from council.dialect.trace import Trace
from council.symbolic.verify.ispl import trace_to_ispl
from council.symbolic.verify.ltlf import parse


def _mcmas_available() -> bool:
    return shutil.which("mcmas") is not None


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1" or not _mcmas_available(),
    reason="RUN_INTEGRATION=1 required and mcmas must be on PATH",
)


def _build_4_agent_4_round_trace() -> Trace:
    t = Trace()
    t = t.append(Propose(move_id="p0", agent_id="A", round_index=0,
                         claim=Claim(surface="x", evidence=("e1",))))
    t = t.append(Challenge(move_id="c1", agent_id="B", round_index=0))
    t = t.append(Concede(move_id="cc2", agent_id="C", round_index=1))
    t = t.append(Vote(move_id="v3", agent_id="D", round_index=1,
                      option=Claim(surface="yes", evidence=("e2",))))
    return t


def _run_mcmas(ispl_text: str) -> tuple[int, str, str]:
    """Run mcmas on the given ISPL text; return (returncode, stdout, stderr)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ispl", delete=False) as f:
        f.write(ispl_text)
        path = Path(f.name)
    try:
        proc = subprocess.run(
            ["mcmas", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return proc.returncode, proc.stdout, proc.stderr
    finally:
        path.unlink(missing_ok=True)


def test_mcmas_verifies_eventually_decide_and_refutation_reachable() -> None:
    """W1 acceptance criterion (master plan §7 W1).

    On the 4-agent / 4-round canonical trace, MCMAS must report that both
    EventuallyDecide (EF is_vote) and RefutationReachable (EF(is_challenge &
    EF(is_vote))) are TRUE.
    """
    trace = _build_4_agent_4_round_trace()
    ispl = trace_to_ispl(
        trace,
        [parse("F(is_vote)"), parse("F(is_challenge && F(is_vote))")],
        agent_ids=("A", "B", "C", "D"),
    )
    rc, stdout, stderr = _run_mcmas(ispl)
    assert rc == 0, f"mcmas exit {rc}: stderr={stderr!r}"
    # MCMAS reports each formula as TRUE/FALSE in stdout
    assert "TRUE" in stdout, f"Expected TRUE verdicts in mcmas output: {stdout!r}"
    # Both formulae should be present in output
    assert stdout.count("TRUE") >= 2, (
        f"Expected at least 2 TRUE verdicts (EventuallyDecide + RefutationReachable), "
        f"got {stdout.count('TRUE')}: {stdout!r}"
    )
