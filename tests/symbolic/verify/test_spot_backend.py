"""Tests for council/symbolic/verify/spot_backend.py — SPOT-backed LTL3 monitor.

SPOT is an optional dependency installed via apt/brew/source (see
docs/installation.md). When SPOT is unavailable, SPOTMonitor tests are skipped
and only the make_monitor() fallback path is exercised.
"""

import pytest

from council.symbolic.verify.ltl2mon_backend import ProgressionMonitor
from council.symbolic.verify.ltlf import parse
from council.symbolic.verify.monitor import LTL3Monitor, Verdict
from council.symbolic.verify.spot_backend import (
    SPOTMonitor,
    is_spot_available,
    make_monitor,
)

# ---------------------------------------------------------------------------
# is_spot_available — boolean detection
# ---------------------------------------------------------------------------

def test_is_spot_available_returns_bool() -> None:
    """is_spot_available returns a bool — never raises, regardless of environment."""
    assert isinstance(is_spot_available(), bool)


# ---------------------------------------------------------------------------
# SPOTMonitor — gated by SPOT availability
# ---------------------------------------------------------------------------

skip_if_no_spot = pytest.mark.skipif(
    not is_spot_available(),
    reason="SPOT Python bindings not installed — see docs/installation.md",
)


def test_spot_monitor_raises_import_error_when_spot_unavailable() -> None:
    """If SPOT is not installed, direct SPOTMonitor() construction raises ImportError."""
    if is_spot_available():
        pytest.skip("This test verifies the no-SPOT path; SPOT is installed.")
    with pytest.raises(ImportError, match=r"SPOT.*not installed"):
        SPOTMonitor(parse("F(p)"))


@skip_if_no_spot
def test_spot_monitor_finally_top() -> None:
    """SPOTMonitor on F(p): TOP after observing p=True."""
    m = SPOTMonitor(parse("F(p)"))
    assert m.step({"p": False}) is Verdict.UNKNOWN
    assert m.step({"p": True}) is Verdict.TOP


@skip_if_no_spot
def test_spot_monitor_globally_bottom() -> None:
    """SPOTMonitor on G(p): BOTTOM after observing p=False."""
    m = SPOTMonitor(parse("G(p)"))
    assert m.step({"p": True}) is Verdict.UNKNOWN
    assert m.step({"p": False}) is Verdict.BOTTOM


@skip_if_no_spot
def test_spot_monitor_implements_ltl3monitor_abc() -> None:
    m = SPOTMonitor(parse("F(p)"))
    assert isinstance(m, LTL3Monitor)


@skip_if_no_spot
def test_spot_monitor_reset_restores_unknown() -> None:
    m = SPOTMonitor(parse("F(p)"))
    m.step({"p": True})
    assert m.current_verdict is Verdict.TOP
    m.reset()
    assert m.current_verdict is Verdict.UNKNOWN


@skip_if_no_spot
@pytest.mark.parametrize(("formula_str", "events"), [
    ("F(p)", [{"p": False}, {"p": False}, {"p": True}]),
    ("G(p)", [{"p": True}, {"p": True}, {"p": False}]),
    ("p U q", [{"p": True, "q": False}, {"p": True, "q": True}]),
])
def test_spot_monitor_agrees_with_progression(
    formula_str: str, events: list[dict[str, object]],
) -> None:
    """SPOTMonitor and ProgressionMonitor must produce the same final verdict."""
    sm = SPOTMonitor(parse(formula_str))
    pm = ProgressionMonitor(parse(formula_str))
    final_spot, final_prog = Verdict.UNKNOWN, Verdict.UNKNOWN
    for e in events:
        final_spot = sm.step(e)
        final_prog = pm.step(e)
    assert final_spot is final_prog


# ---------------------------------------------------------------------------
# make_monitor — factory always works regardless of SPOT availability
# ---------------------------------------------------------------------------

def test_make_monitor_returns_ltl3monitor() -> None:
    """make_monitor always returns an LTL3Monitor instance."""
    m = make_monitor(parse("F(p)"))
    assert isinstance(m, LTL3Monitor)


def test_make_monitor_prefer_spot_false_returns_progression_monitor() -> None:
    """prefer_spot=False always returns ProgressionMonitor."""
    m = make_monitor(parse("F(p)"), prefer_spot=False)
    assert isinstance(m, ProgressionMonitor)


def test_make_monitor_default_prefer_spot_when_unavailable() -> None:
    """When SPOT is not installed, default make_monitor() falls back to ProgressionMonitor."""
    if is_spot_available():
        pytest.skip("This test verifies the no-SPOT fallback; SPOT is installed.")
    m = make_monitor(parse("F(p)"))
    assert isinstance(m, ProgressionMonitor)


@skip_if_no_spot
def test_make_monitor_default_prefer_spot_when_available() -> None:
    """When SPOT is installed, default make_monitor() returns SPOTMonitor."""
    m = make_monitor(parse("F(p)"))
    assert isinstance(m, SPOTMonitor)


def test_make_monitor_steps_correctly() -> None:
    """make_monitor result behaves as an LTL3Monitor regardless of backend."""
    m = make_monitor(parse("F(p)"))
    assert m.current_verdict is Verdict.UNKNOWN
    v = m.step({"p": True})
    assert v is Verdict.TOP


def test_make_monitor_handles_full_fragment_via_fallback() -> None:
    """make_monitor handles X/U/W via ProgressionMonitor regardless of prefer_spot."""
    # Even without SPOT, full-fragment formulas work via fallback
    m = make_monitor(parse("X(p)"), prefer_spot=False)
    assert m.step({"p": False}) is Verdict.UNKNOWN  # X consumed; residual = p
    assert m.step({"p": True}) is Verdict.TOP
