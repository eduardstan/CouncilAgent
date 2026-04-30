"""T3 counterexample mechanised on MCMAS — partial mechanisation of theorem T3.

T3 statement (`docs/theory.md` §T3):
    There exists a CTLK invariant — `G(consensus → ∃i. K_i evidenceFor(consensus))`
    — that no purely vote-counting aggregator satisfies.

The proof sketch is a counterexample: 3 agents emitting `Vote("X")` with
EMPTY evidence reach unanimous "consensus" yet violate the propositional
weakening `G(is_vote -> has_evidence)` (= the W1 property
`ProvenanceCompleteness`). This test sends that counterexample to MCMAS
and asserts the model checker reports `FALSE` on the formula — mechanically
confirming what the W1 monitor reports as `Verdict.BOTTOM`.

This is the ADR-0005 partial T3 mechanisation: the COUNTEREXAMPLE is now
MCMAS-verified. The full ablation row vs. `MajorityVote`/`BordaCount`/
`CondorcetAggregation` is W2/P1 work because those aggregators are not yet
implemented.

Gated by RUN_INTEGRATION=1 AND `mcmas` on PATH (same convention as
test_mcmas_offline.py).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from council.dialect.moves import Claim, Vote
from council.dialect.trace import Trace
from council.symbolic.verify.ispl import trace_to_ispl
from council.symbolic.verify.ltlf import parse


def _mcmas_available() -> bool:
    return shutil.which("mcmas") is not None


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1" or not _mcmas_available(),
    reason="RUN_INTEGRATION=1 required and mcmas must be on PATH (see ADR-0005)",
)


def _build_unanimous_vote_without_evidence_trace() -> Trace:
    """3 agents, each emits Vote('X') with empty evidence — the canonical T3
    counterexample described in docs/theory.md §T3."""
    t = Trace()
    for i, aid in enumerate(("A", "B", "C")):
        t = t.append(Vote(
            move_id=f"v{i}",
            agent_id=aid,
            round_index=0,
            option=Claim(surface="X", evidence=()),  # empty: the counterexample
        ))
    return t


def _run_mcmas(ispl_text: str) -> tuple[int, str, str]:
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


def test_mcmas_rejects_provenance_completeness_on_unanimous_no_evidence_trace() -> None:
    """T3 counterexample mechanisation.

    On the 3-agent unanimous-vote-without-evidence trace, MCMAS must report
    `G(is_vote -> has_evidence)` = `AG(is_vote -> has_evidence)` as FALSE.
    This is the propositional weakening of T3's CTLK invariant; MCMAS
    confirming FALSE here mechanically confirms the W1 monitor's
    `Verdict.BOTTOM` on the same trace.
    """
    trace = _build_unanimous_vote_without_evidence_trace()
    ispl = trace_to_ispl(
        trace,
        [parse("G(is_vote -> has_evidence)")],
        agent_ids=("A", "B", "C"),
    )
    rc, stdout, stderr = _run_mcmas(ispl)
    assert rc == 0, f"mcmas exit {rc}: stderr={stderr!r}"
    assert "is FALSE in the model" in stdout, (
        f"Expected MCMAS to report the formula as FALSE, got stdout={stdout!r}"
    )
    # Belt-and-braces: not a TRUE-line for this formula
    assert "is TRUE in the model" not in stdout, (
        f"Unexpected TRUE verdict for the counterexample formula: {stdout!r}"
    )


def test_mcmas_accepts_provenance_completeness_when_all_votes_have_evidence() -> None:
    """Sanity-check sibling: same shape but with non-empty evidence — MCMAS
    should report TRUE. Without this we cannot rule out a false-positive
    where MCMAS rejects on a benign trace too."""
    t = Trace()
    for i, aid in enumerate(("A", "B", "C")):
        t = t.append(Vote(
            move_id=f"v{i}",
            agent_id=aid,
            round_index=0,
            option=Claim(surface="X", evidence=("e1",)),  # non-empty
        ))
    ispl = trace_to_ispl(
        t,
        [parse("G(is_vote -> has_evidence)")],
        agent_ids=("A", "B", "C"),
    )
    rc, stdout, _stderr = _run_mcmas(ispl)
    assert rc == 0
    assert "is TRUE in the model" in stdout
