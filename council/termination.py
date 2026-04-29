"""L0 — TerminationStrategy ABC + concrete strategies.

All strategies (except `LTLfMonitorTermination`) are pure functions over
(Trace, round_index) — no model calls.

W1/PR8 adds:
- `MonitorVerdict`: a per-round per-property record collected by the L1 monitor
  termination strategy (referenced by ProvenanceReceipt.monitor_verdicts).
- `LTLfMonitorTermination`: stateful strategy that steps each LTL_f monitor over
  the trace's events, queues an Intervention on Verdict.BOTTOM, and reports
  violations to `core.run_council()`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from council.dialect.trace import Trace

if TYPE_CHECKING:
    from council.symbolic.verify.interventions import Intervention
    from council.symbolic.verify.monitor import LTL3Monitor, Property


class TerminationStrategy(ABC):
    """Decides whether a council run should stop."""

    @abstractmethod
    def should_stop(self, trace: Trace, round_index: int) -> tuple[bool, str]: ...


@dataclass(frozen=True, slots=True)
class FixedRounds(TerminationStrategy):
    """Stop after a fixed number of deliberation rounds."""

    max_rounds: int = 2

    def should_stop(self, trace: Trace, round_index: int) -> tuple[bool, str]:
        if round_index >= self.max_rounds:
            return (True, f"FixedRounds({self.max_rounds})")
        return (False, "")


class CompositeTermination(TerminationStrategy):
    """Stop as soon as any constituent strategy fires."""

    def __init__(self, strategies: list[TerminationStrategy]) -> None:
        self._strategies = strategies

    def should_stop(self, trace: Trace, round_index: int) -> tuple[bool, str]:
        for strategy in self._strategies:
            stop, reason = strategy.should_stop(trace, round_index)
            if stop:
                return (True, reason)
        return (False, "")

    @property
    def strategies(self) -> tuple[TerminationStrategy, ...]:
        """Read-only view of the constituent strategies (for traversal callers)."""
        return tuple(self._strategies)


# ---------------------------------------------------------------------------
# MonitorVerdict — referenced by ProvenanceReceipt
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class MonitorVerdict:
    """Single LTL3 monitor verdict snapshot (W1 PR8).

    Collected by LTLfMonitorTermination on every should_stop() call and threaded
    into ProvenanceReceipt.monitor_verdicts by run_council().
    """

    property_name: str
    verdict: str  # Verdict enum value: "top" / "bottom" / "unknown"
    round_index: int


# ---------------------------------------------------------------------------
# LTLfMonitorTermination — wires the L1 spine into the pipeline (W1 PR8)
# ---------------------------------------------------------------------------

class LTLfMonitorTermination(TerminationStrategy):
    """Steps a list of LTL_f Property monitors over the trace's events.

    On Verdict.BOTTOM from any monitor, queues the configured Intervention for
    `core.run_council()` to consume before the next round, and reports
    `(True, property_name)` from `should_stop()`. The pipeline applies the
    intervention, increments the intervention counter, and continues unless
    `max_interventions` is exhausted.

    State (not a frozen dataclass — must track stepping progress):
      _last_event_idx: int — events with index < this have already been stepped
      _pending: Intervention | None — queued for next pipeline tick
      _intervention_count: int — total interventions applied this run
      _verdicts: list[MonitorVerdict] — accumulator drained per round
    """

    def __init__(
        self,
        properties: list[Property],
        on_violation: Intervention | None = None,
        max_interventions: int = 3,
    ) -> None:
        from council.symbolic.verify.monitor import LTL3Monitor  # noqa: F401  runtime import

        self._properties = list(properties)
        self._compiled: list[tuple[Property, LTL3Monitor]] = [
            (p, p.compile()) for p in properties
        ]
        self._on_violation = on_violation
        self._max_interventions = max_interventions
        self._last_event_idx = 0
        self._pending: Intervention | None = None
        self._intervention_count = 0
        self._verdicts: list[MonitorVerdict] = []

    def should_stop(self, trace: Trace, round_index: int) -> tuple[bool, str]:
        """Step monitors over new events; report first violation if any."""
        if self._intervention_count >= self._max_interventions:
            return (True, "max-interventions-exhausted")

        events = trace.to_events()
        # Step monitors over events not yet seen
        new_events = events[self._last_event_idx:]
        violation_name: str | None = None
        for event in new_events:
            for prop, monitor in self._compiled:
                v = monitor.step(event)
                self._verdicts.append(
                    MonitorVerdict(
                        property_name=prop.name,
                        verdict=v.value,
                        round_index=round_index,
                    ),
                )
                # First violation in this batch wins
                if violation_name is None and v.value == "bottom":
                    violation_name = prop.name
        self._last_event_idx = len(events)

        if violation_name is not None:
            self._pending = self._on_violation
            return (True, violation_name)
        return (False, "")

    def pending_intervention(self) -> Intervention | None:
        """Return the queued intervention exactly once; subsequent calls return None."""
        intervention = self._pending
        self._pending = None
        return intervention

    def acknowledge_intervention(self) -> None:
        """Record that an intervention has been applied (increments counter)."""
        self._intervention_count += 1

    def consume_verdicts(self) -> tuple[MonitorVerdict, ...]:
        """Drain the verdict accumulator (called by run_council per round)."""
        verdicts = tuple(self._verdicts)
        self._verdicts = []
        return verdicts

    def find_property(self, name: str) -> Property | None:
        """Look up a configured Property by name. Returns None if absent."""
        for prop, _ in self._compiled:
            if prop.name == name:
                return prop
        return None

    def reset(self) -> None:
        """Reset all monitors and internal state — for reuse across run_council calls."""
        for _, monitor in self._compiled:
            monitor.reset()
        self._last_event_idx = 0
        self._pending = None
        self._intervention_count = 0
        self._verdicts = []
