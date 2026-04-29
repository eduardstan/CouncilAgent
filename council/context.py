"""Council runtime types — CouncilContext, Confidence union, CouncilResponse, ProvenanceReceipt.

All value objects are frozen+slots. The Confidence union (§5) has four tagged subtypes;
plurality fraction is type-impossible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from council.dialect.moves import Move, Vote
from council.dialect.trace import Trace
from council.models import ModelClient
from council.termination import MonitorVerdict, TerminationStrategy
from council.tools import ToolClient
from council.topology import Topology

#: Synthetic moderator agent ID used for all moves injected by W1 Interventions.
#: Lives in core (context.py) because is_complete() needs it for the §11
#: bottom-verdict-intervention check; interventions.py re-imports it.
INTERVENTION_AGENT_ID = "_w1_intervention"

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
    monitor_verdicts: tuple[MonitorVerdict, ...] = ()
    asp_groundings: tuple[str, ...] = ()
    cost_ledger: tuple[tuple[str, float], ...] = ()
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    def is_complete(self) -> bool:
        """Constitution §11 receipt-completeness check.

        Returns True iff:
          (a) every move in the trace has a cost entry (intervention moves
              must use cost=0.0 — they are symbolic, not model-charged);
          (b) every Vote in the trace carries at least one evidence atom
              (Votes are committed decisions and must justify themselves);
          (c) every BOTTOM monitor verdict is followed by an intervention
              move (a move from INTERVENTION_AGENT_ID at >= the verdict's
              round_index) — every ⊥ verdict triggered an intervention.

        The QBAF-argument-count clause from §11 is W2 territory and is
        evaluated separately when self.qbaf is not None (deferred).
        """
        if not self.trace.moves:
            return True

        # (a) cost-ledger clause
        cost_keys = {k for k, _ in self.cost_ledger}
        if not all(m.move_id in cost_keys for m in self.trace.moves):
            return False

        # (b) Vote-evidence clause
        for m in self.trace.moves:
            if isinstance(m, Vote) and not m.option.evidence:
                return False

        # (c) bottom-verdict-intervention clause
        for v in self.monitor_verdicts:
            if v.verdict == "bottom":
                covered = any(
                    m.agent_id == INTERVENTION_AGENT_ID
                    and m.round_index >= v.round_index
                    for m in self.trace.moves
                )
                if not covered:
                    return False

        return True


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
