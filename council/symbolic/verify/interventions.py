"""L1 verification — Intervention ABC + 5 concrete implementations.

Constitution §12: "The verifier can intervene." When an LTL_f monitor returns
Verdict.BOTTOM, the configured Intervention executes before the next
deliberation round, redirecting deliberation rather than just observing it.

This module is the ONLY L1 file that imports from council/dialect/moves.py
(architecture.md approved exception 4) — it injects typed Move objects into
the trace on violation.

The 5 concrete interventions:
  - ReprompCorrective: synthetic Question targeting the offending agent
  - ForceChallenge:    devil's-advocate Challenge against the last Propose
  - TriggerVerifier:   invoke ctx.tool_client (Z3/clingo/Lean); record as Clarify
  - EscalateModel:     Abstain from offending agent + placeholder upgraded Propose
  - FreezeAndAccept:   identity (no injection); records the violation in receipts

All interventions are async to match the master-plan §6.4 contract; most do not
await anything in PR7 except TriggerVerifier (which awaits ctx.tool_client.call()).
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from council.dialect.moves import (
    Abstain,
    Challenge,
    Claim,
    ClaimDomain,
    Clarify,
    Force,
    Propose,
    Question,
)
from council.dialect.trace import Trace
from council.tools import ToolFailure, ToolRequest

if TYPE_CHECKING:
    from council.context import CouncilContext
    from council.symbolic.verify.monitor import Property

logger = logging.getLogger(__name__)

#: Synthetic moderator agent ID used for all injected moves.
INTERVENTION_AGENT_ID = "_w1_intervention"


def _next_move_id(violated_name: str, trace_len: int) -> str:
    """Deterministic move_id for an intervention move: stable across reruns."""
    seed = f"{violated_name}:{trace_len}"
    return f"intervention-{uuid.uuid5(uuid.NAMESPACE_OID, seed)}"


def _current_round_index(trace: Trace) -> int:
    """Return the round_index of the most recent move, or 0 for an empty trace."""
    if not trace.moves:
        return 0
    return max(m.round_index for m in trace.moves)


# ---------------------------------------------------------------------------
# Intervention ABC
# ---------------------------------------------------------------------------

class Intervention(ABC):
    """Executed when a Property monitor returns Verdict.BOTTOM.

    Returns a new Trace (possibly with injected Moves). Must not call generation
    models on the headline path; model calls are restricted to EscalateModel
    (and even there, deferred to PR8).
    """

    @abstractmethod
    async def execute(
        self,
        trace: Trace,
        violated: Property,
        ctx: CouncilContext,
    ) -> Trace:
        """Apply the intervention. Returns the new trace (possibly augmented)."""
        ...


# ---------------------------------------------------------------------------
# 1. ReprompCorrective — inject a Question that re-prompts the offender
# ---------------------------------------------------------------------------

class ReprompCorrective(Intervention):
    """Re-prompt with the violated-property description.

    Injects a Question move from the synthetic moderator. The query.surface
    cites the violated property name, providing the next round's context for
    council agents to address.
    """

    async def execute(
        self,
        trace: Trace,
        violated: Property,
        ctx: CouncilContext,
    ) -> Trace:
        target = trace.moves[-1].agent_id if trace.moves else ""
        query = Claim(
            surface=f"[Monitor intervention: re-address {violated.name}]",
            domain=ClaimDomain.FREE,
        )
        question = Question(
            move_id=_next_move_id(violated.name, len(trace.moves)),
            agent_id=INTERVENTION_AGENT_ID,
            round_index=_current_round_index(trace),
            target=target,
            query=query,
        )
        return trace.append(question)


# ---------------------------------------------------------------------------
# 2. ForceChallenge — inject a Challenge against the last Propose
# ---------------------------------------------------------------------------

class ForceChallenge(Intervention):
    """Insert a devil's-advocate Challenge against the last Propose.

    "LLM-Modulo at the dialogue level" (Kambhampati ICML 2024): a typed
    intervention that forces the council to address the violated property.
    The Challenge's reason.surface contains the violated property's name.
    """

    async def execute(
        self,
        trace: Trace,
        violated: Property,
        ctx: CouncilContext,
    ) -> Trace:
        # Find the most recent Propose move to target
        proposes = trace.by_force(Force.PROPOSE)
        target = proposes[-1].move_id if proposes else ""
        reason = Claim(
            surface=f"[Monitor intervention: {violated.name}]",
            domain=ClaimDomain.FREE,
        )
        challenge = Challenge(
            move_id=_next_move_id(violated.name, len(trace.moves)),
            agent_id=INTERVENTION_AGENT_ID,
            round_index=_current_round_index(trace),
            target=target,
            reason=reason,
        )
        return trace.append(challenge)


# ---------------------------------------------------------------------------
# 3. TriggerVerifier — invoke ctx.tool_client; record result as Clarify
# ---------------------------------------------------------------------------

class TriggerVerifier(Intervention):
    """Invoke a symbolic verifier (Z3/clingo/Lean) via ctx.tool_client.

    Injects a Clarify move with the verifier's output. When ctx.tool_client is
    None (W0 default), the trace is returned unchanged and a debug log is
    emitted — graceful degradation per the spec.
    """

    def __init__(self, tool_name: str = "z3") -> None:
        self.tool_name = tool_name

    async def execute(
        self,
        trace: Trace,
        violated: Property,
        ctx: CouncilContext,
    ) -> Trace:
        if ctx.tool_client is None:
            logger.debug(
                "TriggerVerifier: ctx.tool_client is None; "
                "skipping intervention for %s", violated.name,
            )
            return trace

        request = ToolRequest(
            tool=self.tool_name,
            payload={"property": violated.name, "formula": violated.formula},
        )
        result = await ctx.tool_client.call(request)
        if isinstance(result, ToolFailure):
            output = f"[verifier {self.tool_name} failed: {result.error}]"
        else:
            output = f"[verifier {self.tool_name}: {result.result!r}]"

        clarify = Clarify(
            move_id=_next_move_id(violated.name, len(trace.moves)),
            agent_id=INTERVENTION_AGENT_ID,
            round_index=_current_round_index(trace),
            target=trace.moves[-1].move_id if trace.moves else "",
            restated=Claim(surface=output, domain=ClaimDomain.FREE),
        )
        return trace.append(clarify)


# ---------------------------------------------------------------------------
# 4. EscalateModel — Abstain offender + placeholder upgraded Propose
# ---------------------------------------------------------------------------

class EscalateModel(Intervention):
    """Bump the offending agent to a stronger model tier.

    PR7 deterministic version: injects (a) an Abstain move from the offending
    agent and (b) a placeholder Propose from the synthetic moderator with a
    surface marker indicating the upgraded model. The actual model.complete()
    call is wired in PR8 (LTLfMonitorTermination + core.py loop) once the
    prompt context is available.
    """

    def __init__(self, upgraded_model: str = "anthropic/claude-3.5-sonnet") -> None:
        self.upgraded_model = upgraded_model

    async def execute(
        self,
        trace: Trace,
        violated: Property,
        ctx: CouncilContext,
    ) -> Trace:
        # Identify the offending agent: most recent Propose author, or fall back to
        # the most recent move's author.
        proposes = trace.by_force(Force.PROPOSE)
        if proposes:
            offender = proposes[-1].agent_id
        elif trace.moves:
            offender = trace.moves[-1].agent_id
        else:
            offender = ""

        round_index = _current_round_index(trace)

        abstain = Abstain(
            move_id=_next_move_id(violated.name + ":abstain", len(trace.moves)),
            agent_id=offender,
            round_index=round_index,
            why=f"[escalation: violated {violated.name}]",
        )
        new_trace = trace.append(abstain)

        upgraded = Propose(
            move_id=_next_move_id(violated.name + ":upgrade", len(new_trace.moves)),
            agent_id=INTERVENTION_AGENT_ID,
            round_index=round_index,
            claim=Claim(
                surface=f"[escalated to {self.upgraded_model}]",
                domain=ClaimDomain.FREE,
            ),
        )
        return new_trace.append(upgraded)


# ---------------------------------------------------------------------------
# 5. FreezeAndAccept — identity intervention; logs but does not inject
# ---------------------------------------------------------------------------

class FreezeAndAccept(Intervention):
    """Accept the partial result without additional moves.

    The violation is recorded in the ProvenanceReceipt's monitor_verdicts
    (PR8 wiring); this intervention itself returns the unchanged trace.
    Useful as a fallback after max_interventions has been exhausted.
    """

    async def execute(
        self,
        trace: Trace,
        violated: Property,
        ctx: CouncilContext,
    ) -> Trace:
        logger.info(
            "FreezeAndAccept: violation of %s acknowledged; trace unchanged",
            violated.name,
        )
        return trace
