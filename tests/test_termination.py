"""Tests for council/termination.py — TerminationStrategy ABC + concrete impls."""

from __future__ import annotations

import pytest

from council.dialect.trace import Trace


def test_fixed_rounds_stops_at_limit() -> None:
    from council.termination import FixedRounds

    fr = FixedRounds(max_rounds=3)
    stop, reason = fr.should_stop(Trace(), 3)
    assert stop is True
    assert "3" in reason


def test_fixed_rounds_continues_before_limit() -> None:
    from council.termination import FixedRounds

    fr = FixedRounds(max_rounds=3)
    stop, _ = fr.should_stop(Trace(), 2)
    assert stop is False


def test_fixed_rounds_stops_at_zero_rounds() -> None:
    from council.termination import FixedRounds

    fr = FixedRounds(max_rounds=0)
    stop, _ = fr.should_stop(Trace(), 0)
    assert stop is True


def test_fixed_rounds_is_frozen() -> None:
    from council.termination import FixedRounds
    import dataclasses

    fr = FixedRounds(max_rounds=2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        fr.max_rounds = 99  # type: ignore[misc]


def test_composite_stops_if_any_strategy_fires() -> None:
    from council.termination import CompositeTermination, FixedRounds

    comp = CompositeTermination([FixedRounds(2), FixedRounds(5)])
    stop, reason = comp.should_stop(Trace(), 2)
    assert stop is True
    assert reason != ""


def test_composite_continues_if_no_strategy_fires() -> None:
    from council.termination import CompositeTermination, FixedRounds

    comp = CompositeTermination([FixedRounds(3), FixedRounds(5)])
    stop, _ = comp.should_stop(Trace(), 1)
    assert stop is False


def test_composite_first_firing_strategy_wins() -> None:
    from council.termination import CompositeTermination, FixedRounds

    comp = CompositeTermination([FixedRounds(1), FixedRounds(3)])
    stop, reason = comp.should_stop(Trace(), 1)
    assert stop is True
    assert "1" in reason


def test_composite_empty_strategies_never_stops() -> None:
    from council.termination import CompositeTermination

    comp = CompositeTermination([])
    stop, _ = comp.should_stop(Trace(), 100)
    assert stop is False
