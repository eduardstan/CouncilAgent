"""Council runtime types — CouncilContext, Confidence union, CouncilResponse, ProvenanceReceipt.

All value objects are frozen+slots. The Confidence union (§5) has four tagged subtypes;
plurality fraction is type-impossible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from council.dialect.moves import Move
from council.dialect.trace import Trace
from council.models import ModelClient
from council.termination import TerminationStrategy
from council.tools import ToolClient
from council.topology import Topology

# Defer import of ProtocolAutomaton to avoid circular — imported at function call sites


# ---------------------------------------------------------------------------
# Confidence tagged union — Constitution §5
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class JSDConfidence:
    value: float
    tag: ClassVar[str] = "jsd"


@dataclass(frozen=True, slots=True)
class BAFMarginConfidence:
    value: float
    tag: ClassVar[str] = "baf"


@dataclass(frozen=True, slots=True)
class MonitorVerdictConfidence:
    value: float
    tag: ClassVar[str] = "monitor"


@dataclass(frozen=True, slots=True)
class CopelandConfidence:
    value: float
    tag: ClassVar[str] = "copeland"


Confidence = JSDConfidence | BAFMarginConfidence | MonitorVerdictConfidence | CopelandConfidence


# ---------------------------------------------------------------------------
# ProvenanceReceipt — per-run symbolic outputs (Constitution §11)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ProvenanceReceipt:
    trace: Trace
    qbaf: object | None = None
    monitor_verdicts: tuple[object, ...] = ()
    asp_groundings: tuple[str, ...] = ()
    cost_ledger: tuple[tuple[str, float], ...] = ()
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    def is_complete(self) -> bool:
        """True iff every move in the trace has a cost entry."""
        if not self.trace.moves:
            return True
        cost_keys = {k for k, _ in self.cost_ledger}
        return all(m.move_id in cost_keys for m in self.trace.moves)


# ---------------------------------------------------------------------------
# VisibilityContext — anonymisation carrier (Constitution §10)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class VisibilityContext:
    """Per-agent view of the trace; carries the anonymise flag from the single anonymisation site."""

    visible_moves: tuple[Move, ...]
    agent_id: str
    anonymize: bool
    round_index: int


# ---------------------------------------------------------------------------
# CouncilContext — immutable configuration passed to run_council
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CouncilContext:
    agents: tuple[str, ...]
    model_client: ModelClient
    protocol: object  # ProtocolAutomaton — declared as object to avoid circular import
    topology: Topology
    termination: TerminationStrategy
    anonymize: bool = True
    original_question: str = ""
    tool_client: ToolClient | None = None  # wired by TriggerVerifier intervention (W1)


# ---------------------------------------------------------------------------
# CouncilState — immutable pipeline snapshot between rounds
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CouncilState:
    trace: Trace
    round_index: int
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# CouncilResponse — the outward-facing result (same interface as a single LLM call)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CouncilResponse:
    answer: str
    confidence: Confidence
    receipt: ProvenanceReceipt
