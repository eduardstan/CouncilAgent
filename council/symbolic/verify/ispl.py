"""L1 verification — Trace + formulae -> ISPL text emitter for MCMAS.

Encodes a finite Trace as a deterministic Kripke structure in ISPL (the
interpreted-system specification language used by MCMAS, Lomuscio-Qu-Raimondi
2017). The encoding is bounded model checking: a single Environment agent
advances a `position` counter through each move, and per-position evaluations
expose the trace's atomic propositions for CTL specifications.

This module produces text only — subprocess invocation of MCMAS lives in
tests/integration/ (Constitution §8: no system-tool calls from council/).

LTL_f to CTL translation:
  - Atom(name)            -> name
  - Neg(phi)              -> !translate(phi)
  - And/Or/Implies        -> & / | / ->
  - Finally(phi)          -> EF(translate(phi))
  - Globally(phi)         -> AG(translate(phi))
  - Next(phi)             -> EX(translate(phi))
  - Until(phi, psi)       -> E[translate(phi) U translate(psi)]
  - WeakUntil(phi, psi)   -> E[translate(phi) U translate(psi)] | AG(translate(phi))

The temporal operators X, U, W are best-effort translations; for the formulas
in PROPERTY_REGISTRY the EF/AG forms suffice (deterministic-trace encoding).
"""

from __future__ import annotations

from collections.abc import Iterable

from council.dialect.trace import Trace
from council.symbolic.verify.ltlf import (
    And,
    Atom,
    Boolean,
    Finally,
    Globally,
    Implies,
    LTLf,
    Neg,
    Next,
    Or,
    Until,
    WeakUntil,
)

# ---------------------------------------------------------------------------
# LTL_f -> CTL translation
# ---------------------------------------------------------------------------

def ltlf_to_ctl(formula: LTLf) -> str:
    """Translate an LTL_f AST into MCMAS-compatible CTL syntax.

    For deterministic-trace encodings, EF/AG are equivalent to their LTL F/G
    counterparts on the unique computation path.
    """
    match formula:
        case Boolean(value=v):
            return "true" if v else "false"
        case Atom(name=n):
            return n
        case Neg(arg=a):
            return f"!{ltlf_to_ctl(a)}"
        case And(left=lf, right=rf):
            return f"({ltlf_to_ctl(lf)} and {ltlf_to_ctl(rf)})"
        case Or(left=lf, right=rf):
            return f"({ltlf_to_ctl(lf)} or {ltlf_to_ctl(rf)})"
        case Implies(left=lf, right=rf):
            return f"({ltlf_to_ctl(lf)} -> {ltlf_to_ctl(rf)})"
        case Finally(arg=a):
            return f"EF({ltlf_to_ctl(a)})"
        case Globally(arg=a):
            return f"AG({ltlf_to_ctl(a)})"
        case Next(arg=a):
            return f"EX({ltlf_to_ctl(a)})"
        case Until(left=lf, right=rf):
            return f"E({ltlf_to_ctl(lf)} U {ltlf_to_ctl(rf)})"
        case WeakUntil(left=lf, right=rf):
            return (
                f"(E({ltlf_to_ctl(lf)} U {ltlf_to_ctl(rf)})"
                f" or AG({ltlf_to_ctl(lf)}))"
            )
    raise ValueError(f"ltlf_to_ctl: unsupported formula {formula!r}")


# ---------------------------------------------------------------------------
# ISPL section builders
# ---------------------------------------------------------------------------

def _encode_environment_agent(num_events: int) -> str:
    """Single Environment agent that advances `position` from 0 to num_events.

    The terminal state (position = num_events) loops to itself, allowing CTL
    checks like AG(EF(p)) to evaluate over the full trace prefix.
    """
    final = num_events
    lines = [
        "Agent Environment",
        "  Vars:",
        f"    position : 0..{final};",
        "  end Vars",
        "  Actions = { advance };",
        "  Protocol:",
        "    Other: { advance };",
        "  end Protocol",
        "  Evolution:",
    ]
    if final > 0:
        # position evolves position+1 each step until terminal state
        for i in range(final):
            lines.append(f"    position={i + 1} if position={i} and Action=advance;")
        # Terminal: stay
        lines.append(f"    position={final} if position={final} and Action=advance;")
    else:
        lines.append("    position=0 if position=0 and Action=advance;")
    lines.append("  end Evolution")
    lines.append("end Agent")
    return "\n".join(lines)


def _encode_evaluations(events: tuple[dict[str, object], ...]) -> str:
    """Build the Evaluation section: one clause per (position, AP) where AP is True.

    The boolean APs become evaluation predicates that hold at the matching position.
    Non-boolean keys (force string, agent_id) are encoded as separate predicates
    using `eq` over a position-indexed lookup.
    """
    lines = ["Evaluation"]
    if not events:
        # Need at least one trivially-true evaluation so the file parses
        lines.append("  trace_empty if Environment.position=0;")
    else:
        # For each AP in the schema, emit a single clause that ORs together the
        # positions where it's true.
        ap_keys = _collect_boolean_ap_keys(events)
        for ap in sorted(ap_keys):
            true_positions = [i for i, e in enumerate(events) if bool(e.get(ap, False))]
            if not true_positions:
                # AP never true in this trace → emit a syntactic contradiction
                # that MCMAS accepts as well-typed. We avoid both
                #   `position=-1` (rejected: `out of bound`)
                # and
                #   `position=0 and position!=0` (rejected: `unexpected NOT`,
                #   MCMAS does not accept `!=` in evaluations).
                # `position=0 and position=1` is a pure-`=` contradiction
                # (two distinct in-range constants), provably false at every
                # reachable state and parseable in every MCMAS dialect we know.
                lines.append(f"  {ap} if Environment.position=0 and Environment.position=1;")
                continue
            condition = " or ".join(f"Environment.position={i}" for i in true_positions)
            lines.append(f"  {ap} if {condition};")
    lines.append("end Evaluation")
    return "\n".join(lines)


def _collect_boolean_ap_keys(events: tuple[dict[str, object], ...]) -> set[str]:
    """Collect all keys whose values are bool across all events."""
    keys: set[str] = set()
    for e in events:
        for k, v in e.items():
            if isinstance(v, bool):
                keys.add(k)
    return keys


def _encode_init_states() -> str:
    return "InitStates\n  Environment.position=0;\nend InitStates"


def _encode_groups(agent_ids: tuple[str, ...]) -> str:
    """One Group containing all council agents (placeholder for ATL extensions)."""
    if not agent_ids:
        return "Groups\nend Groups"
    members = ", ".join(_sanitise(a) for a in agent_ids)
    return f"Groups\n  council = {{ {members} }};\nend Groups"


def _encode_formulae(formulae: Iterable[LTLf]) -> str:
    lines = ["Formulae"]
    for f in formulae:
        lines.append(f"  {ltlf_to_ctl(f)};")
    lines.append("end Formulae")
    return "\n".join(lines)


def _sanitise(name: str) -> str:
    """Make `name` a safe ISPL identifier and prefix with `agent_`.

    The prefix prevents collisions with MCMAS's CTL keywords (notably the
    single-letter path quantifiers `A` and `E` and the temporal operators
    `F`, `G`, `X`, `U`). The MCMAS parser otherwise rejects an agent
    declaration like `Agent A` with `unexpected A, expecting identifier`.
    """
    cleaned = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
    return f"agent_{cleaned}" if cleaned else "agent"


def _encode_council_agent(agent_id: str) -> str:
    """A no-op council agent placeholder; participates only in the Groups list.

    A richer encoding (with per-agent state, observation, and ATL formulas) is
    deferred to PR9 where T3 needs strategic operators.
    """
    safe = _sanitise(agent_id)
    return (
        f"Agent {safe}\n"
        f"  Vars:\n"
        f"    role : {{idle}};\n"
        f"  end Vars\n"
        f"  Actions = {{ noop }};\n"
        f"  Protocol:\n"
        f"    Other: {{ noop }};\n"
        f"  end Protocol\n"
        f"  Evolution:\n"
        f"    role=idle if role=idle and Action=noop;\n"
        f"  end Evolution\n"
        f"end Agent"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def trace_to_ispl(
    trace: Trace,
    formulae: Iterable[LTLf],
    *,
    agent_ids: tuple[str, ...] = (),
) -> str:
    """Encode `(trace, formulae, agent_ids)` as an ISPL string for MCMAS.

    The trace is encoded as a deterministic Kripke structure: a single
    Environment agent advances a `position` counter through each move's index;
    per-position atomic propositions populate the Evaluation section. Council
    agents appear as no-op placeholder agents (richer encoding deferred to PR9).

    Each formula is translated to MCMAS-compatible CTL syntax (see
    ltlf_to_ctl). The output is suitable for `mcmas <file>.ispl`.
    """
    events = trace.to_events()
    sections = [
        f"-- Generated by council.symbolic.verify.ispl ({len(events)} events, "
        f"{len(agent_ids)} agents)",
        "",
        _encode_environment_agent(len(events)),
    ]
    for aid in agent_ids:
        sections.append("")
        sections.append(_encode_council_agent(aid))
    sections.append("")
    sections.append(_encode_evaluations(events))
    sections.append("")
    sections.append(_encode_init_states())
    sections.append("")
    sections.append(_encode_groups(agent_ids))
    sections.append("")
    sections.append(_encode_formulae(formulae))
    return "\n".join(sections) + "\n"
