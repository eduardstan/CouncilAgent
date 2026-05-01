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


# ---------------------------------------------------------------------------
# W3 / PR5 — JSD-based termination strategies
# ---------------------------------------------------------------------------

#: Constant returned when no JSD signal is computable (insufficient data,
#: empty rounds). Treated as "no information; do not fire."
_JSD_UNDEFINED: float = -1.0


def _round_distribution(trace: Trace, round_index: int) -> dict[str, float]:
    """Empirical distribution over Propose claim surfaces in round R.

    Each surface's mass is the sum of its Propose ``confidence`` values
    in round R, normalised to sum to 1. Returns an empty dict when the
    round has no Propose moves.
    """
    from council.dialect.moves import Propose

    weights: dict[str, float] = {}
    for move in trace.at_round(round_index):
        if isinstance(move, Propose):
            weights[move.claim.surface] = (
                weights.get(move.claim.surface, 0.0) + move.confidence
            )
    total = sum(weights.values())
    if total <= 0.0:
        return {}
    return {k: v / total for k, v in weights.items()}


def _inter_round_jsd(trace: Trace, round_index: int) -> float:
    """JSD between round-(R-1) and round-R distributions; ``_JSD_UNDEFINED``
    when either round has no proposes (cannot compute a signal)."""
    if round_index <= 0:
        return _JSD_UNDEFINED
    prev = _round_distribution(trace, round_index - 1)
    curr = _round_distribution(trace, round_index)
    if not prev or not curr:
        return _JSD_UNDEFINED
    from council.calibrate.jsd import jsd_divergence

    return jsd_divergence([prev, curr])


def _round_mean_confidence(trace: Trace, round_index: int) -> float:
    """Mean Propose confidence in round R; 0.0 when the round is empty."""
    from council.dialect.moves import Propose

    confs = [
        move.confidence
        for move in trace.at_round(round_index)
        if isinstance(move, Propose)
    ]
    if not confs:
        return 0.0
    return sum(confs) / len(confs)


@dataclass(frozen=True, slots=True)
class JSDDivergenceTermination(TerminationStrategy):
    """Stop when JSD between round-R and round-(R-1) Propose distributions
    drops strictly below ``threshold`` — a "deliberation has stabilised"
    signal grounded in the W3 calibrated-disagreement layer.

    Pure function over (Trace, round_index); no mutable state.
    """

    threshold: float = 0.05

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(
                f"threshold must lie in [0, 1] (got {self.threshold!r})"
            )

    def should_stop(self, trace: Trace, round_index: int) -> tuple[bool, str]:
        jsd = _inter_round_jsd(trace, round_index)
        if jsd == _JSD_UNDEFINED:
            return (False, "")
        if jsd < self.threshold:
            return (True, f"JSDDivergenceTermination(jsd={jsd:.4f}<{self.threshold})")
        return (False, "")


@dataclass(frozen=True, slots=True)
class ConFreezeTermination(TerminationStrategy):
    """Stop when the council has shown ``window`` consecutive rounds of
    low-JSD agreement (each inter-round JSD strictly < ``threshold``)
    and the latest round's mean Propose confidence ≥ ``confidence_floor``.

    The Anonymous 2026 *ConFreeze* paper (OpenReview ``PrqXuAS4BZ``)
    gates on **unanimity in round 0**; we adapt the freeze concept to a
    multi-round JSD-streak setting per the bible (`COUNCIL_NS_PLAN.md`
    §6.4) with the user-confirmed default ``window=5``
    (`specs/w3-calibration.md` §"Resolved decisions" Q4). ADR-0019
    documents the reconciliation.
    """

    window: int = 5
    threshold: float = 0.05
    confidence_floor: float = 0.0

    def __post_init__(self) -> None:
        if self.window < 1:
            raise ValueError(f"window must be ≥ 1 (got {self.window})")
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(
                f"threshold must lie in [0, 1] (got {self.threshold!r})"
            )
        if not 0.0 <= self.confidence_floor <= 1.0:
            raise ValueError(
                f"confidence_floor must lie in [0, 1] "
                f"(got {self.confidence_floor!r})"
            )

    def should_stop(self, trace: Trace, round_index: int) -> tuple[bool, str]:
        if round_index < self.window:
            return (False, "")
        for r in range(round_index - self.window + 1, round_index + 1):
            jsd = _inter_round_jsd(trace, r)
            if jsd == _JSD_UNDEFINED or jsd >= self.threshold:
                return (False, "")
        mean_conf = _round_mean_confidence(trace, round_index)
        if mean_conf < self.confidence_floor:
            return (False, "")
        return (
            True,
            f"ConFreezeTermination(window={self.window},"
            f"threshold={self.threshold},mean_conf={mean_conf:.3f})",
        )
