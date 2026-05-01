"""DeliberationCGS — symbolic concurrent game structure for ATL+CTLK.

Stage 2 of the T7 ATLK revision (specs/t7-atlk-revision.md).

This module models a deliberation as a Moore-synchronous concurrent
game structure (CGS) per MCMAS manual §3.4 (page 29). The
representation is **symbolic**: per-agent local vars, per-agent action
sets, protocol clauses (precondition → enabled actions), and evolution
rules. The state space is left implicit — MCMAS BDDs handle the
explosion at verification time. A small Python-side ``step`` simulator
is provided for the Stage 5 faithfulness test (compare CGS-simulated
runs against ``Trace.append``) and for unit testing.

The canonical headline-theorem instance is provided by
``canonical_t3_cgs(...)``: a 3-agent (alice, bob, carol) CGS that
recovers the T_3 trace under the {Propose, Vote, Abstain} Force
projection. Each agent has a private ``has_witness_p1`` boolean and
a 4-action set; the protocol gates ``propose_with_witness`` on the
witness flag. The public environment tracks per-agent disclosure and
vote flags + a bounded round counter.

Encoding decisions documented in ADR-0020 (Stage 4 of the T7 plan).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from council.symbolic.verify.ispl import ltlf_to_ctl
from council.symbolic.verify.ltlf import LTLf

# Type alias — a Python-side global state for the step simulator.
# Outer key: "Environment" or an agent_id. Inner: var_name → ISPL-string value.
GlobalState = dict[str, dict[str, str]]


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CGSProtocolClause:
    """One line of an agent's ISPL ``Protocol:`` block.

    ``condition`` is an ISPL Boolean expression over the agent's local
    state (and observable environment); ``actions`` is the set of
    actions enabled when the condition is true. ``"Other"`` is the
    catch-all keyword permitted by the ISPL grammar (manual §3.2.1).
    """

    condition: str
    actions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CGSAgentSpec:
    """Specification of one council agent in the CGS."""

    agent_id: str
    actions: tuple[str, ...]
    private_vars: Mapping[str, str]  # var_name → ISPL type ("boolean", "0..3", ...)
    initial_values: Mapping[str, str]  # var_name → ISPL value
    protocol: tuple[CGSProtocolClause, ...]

    def __hash__(self) -> int:
        return hash((
            self.agent_id,
            self.actions,
            tuple(sorted(self.private_vars.items())),
            tuple(sorted(self.initial_values.items())),
            self.protocol,
        ))


@dataclass(frozen=True, slots=True)
class CGSEvolutionRule:
    """One ISPL evolution-function clause.

    Sets ``target_var = new_value`` whenever ``condition`` holds. The
    condition is a Boolean over agent actions and current state.
    """

    target_var: str
    new_value: str
    condition: str


@dataclass(frozen=True, slots=True)
class CGSEnvironmentSpec:
    """Specification of the environment agent in the CGS.

    ``public_vars`` go into the ISPL ``Obsvars`` section (observable
    by all agents — the ``L_E^P`` public component of the environment
    per MCMAS §3.4 page 29).

    ``private_vars`` go into ``Vars`` (the ``L_E^p`` private component;
    invisible to council agents).
    """

    public_vars: Mapping[str, str]
    private_vars: Mapping[str, str]
    initial_values: Mapping[str, str]
    evolution_rules: tuple[CGSEvolutionRule, ...] = ()

    def __hash__(self) -> int:
        return hash((
            tuple(sorted(self.public_vars.items())),
            tuple(sorted(self.private_vars.items())),
            tuple(sorted(self.initial_values.items())),
            self.evolution_rules,
        ))


@dataclass(frozen=True, slots=True)
class CGSAtomicProposition:
    """One atomic proposition definition (an entry in ISPL Evaluation).

    ``expression`` is an ISPL Boolean over agents' and Environment's
    variables.
    """

    name: str
    expression: str


@dataclass(frozen=True, slots=True)
class CGSGroup:
    """One ISPL ``Groups`` entry — a coalition for ATL operators."""

    name: str
    members: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeliberationCGS:
    """Top-level CGS specification.

    ``max_rounds`` bounds the round counter in the public environment
    (matches the ``round`` var's domain). ``initial_state()`` returns
    the unique initial global state (deterministic init); ``step()``
    advances by one Moore-synchronous joint action.
    """

    agents: tuple[CGSAgentSpec, ...]
    environment: CGSEnvironmentSpec
    atomic_propositions: tuple[CGSAtomicProposition, ...]
    groups: tuple[CGSGroup, ...]
    max_rounds: int

    # ------------------------------------------------------------
    # Python-side simulator (used by Stage 5 faithfulness test)
    # ------------------------------------------------------------

    def initial_state(self) -> GlobalState:
        state: GlobalState = {
            "Environment": dict(self.environment.initial_values),
        }
        for agent in self.agents:
            state[agent.agent_id] = dict(agent.initial_values)
        return state

    def is_terminal(self, state: GlobalState) -> bool:
        return state["Environment"].get("round") == str(self.max_rounds)

    def is_action_enabled(
        self, agent_id: str, state: GlobalState, action: str
    ) -> bool:
        agent = self._find_agent(agent_id)
        for clause in agent.protocol:
            if action not in clause.actions:
                continue
            if clause.condition == "Other" or _eval_condition(
                clause.condition, state[agent_id], state["Environment"]
            ):
                return True
        return False

    def step(
        self, state: GlobalState, joint_action: Mapping[str, str]
    ) -> GlobalState:
        """Advance one round under the given joint action.

        Raises ``ValueError`` if any agent's chosen action is not
        enabled by its protocol in the current state.
        """
        if self.is_terminal(state):
            return _copy_state(state)

        # Validate enablement before any update.
        for agent in self.agents:
            chosen = joint_action.get(agent.agent_id)
            if chosen is None:
                raise ValueError(
                    f"joint_action missing entry for {agent.agent_id!r}"
                )
            if not self.is_action_enabled(agent.agent_id, state, chosen):
                raise ValueError(
                    f"action {chosen!r} is not enabled for {agent.agent_id!r} "
                    f"in current state (illegal action)"
                )

        # Apply transitions: each agent's local state may change; the
        # environment's public vars update per the deliberation rules
        # encoded by the canonical_t3 factory.
        new_state = _copy_state(state)
        # Round counter increments (saturates at max_rounds).
        current = int(new_state["Environment"]["round"])
        new_state["Environment"]["round"] = str(min(current + 1, self.max_rounds))
        # Apply per-agent action effects to environment's public flags.
        # The factory encodes the effects in evolution_rules; this
        # implementation interprets them inline for the headline
        # canonical_t3_cgs encoding.
        for agent in self.agents:
            chosen = joint_action[agent.agent_id]
            short = _short_id(agent.agent_id)
            if chosen == "propose_with_witness":
                # Disclosure: env.disclosed_p1_<short> = the agent's witness flag.
                new_state["Environment"][f"disclosed_p1_{short}"] = state[agent.agent_id][
                    "has_witness_p1"
                ]
            elif chosen == "vote_p1":
                new_state["Environment"][f"voted_p1_{short}"] = "true"
        return new_state

    def evaluate_atomic_propositions(
        self, state: GlobalState
    ) -> dict[str, bool]:
        """Evaluate every AP at the given state."""
        return {
            ap.name: _eval_condition(
                ap.expression, {}, state["Environment"], state
            )
            for ap in self.atomic_propositions
        }

    # ------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------

    def _find_agent(self, agent_id: str) -> CGSAgentSpec:
        for agent in self.agents:
            if agent.agent_id == agent_id:
                return agent
        raise KeyError(f"unknown agent_id {agent_id!r}")


def _copy_state(state: GlobalState) -> GlobalState:
    return {scope: dict(vars_) for scope, vars_ in state.items()}


def _short_id(agent_id: str) -> str:
    """Strip the ``agent_`` prefix (matches the canonical_t3 naming)."""
    return agent_id.removeprefix("agent_")


def _eval_condition(
    expression: str,
    local_vars: Mapping[str, str],
    public_env: Mapping[str, str],
    full_state: GlobalState | None = None,
) -> bool:
    """Evaluate a small ISPL Boolean over the given variable bindings.

    Supports the subset used by ``canonical_t3_cgs``: equality on
    Boolean or enumerated values, ``and`` / ``or`` / ``!`` connectives,
    parentheses, and qualified references like ``Environment.foo``
    (looked up from ``full_state`` when present, else from
    ``public_env``). Bare identifiers refer to ``local_vars``.
    """
    namespace: dict[str, Any] = {"True": True, "False": False}
    for var, value in local_vars.items():
        namespace[var] = _coerce(value)
    for var, value in public_env.items():
        namespace[f"Environment_{var}"] = _coerce(value)
    if full_state is not None:
        for scope, vars_ in full_state.items():
            for var, value in vars_.items():
                namespace[f"{scope}_{var}"] = _coerce(value)

    # ISPL → Python: ``=`` becomes ``==``; qualified names (``X.y``)
    # become ``X_y``; ``true``/``false`` become Python literals; ``!``
    # becomes ``not``.
    py_expr = expression.replace(" = ", " == ").replace(".", "_")
    py_expr = _replace_word(py_expr, "true", "True")
    py_expr = _replace_word(py_expr, "false", "False")
    py_expr = py_expr.replace("!", " not ")

    try:
        return bool(eval(py_expr, {"__builtins__": {}}, namespace))
    except (NameError, SyntaxError) as exc:
        raise ValueError(
            f"unable to evaluate ISPL condition {expression!r} "
            f"(translated to {py_expr!r}): {exc}"
        ) from exc


def _replace_word(text: str, word: str, replacement: str) -> str:
    """Word-boundary replacement (does not match inside identifiers)."""
    import re

    return re.sub(rf"\b{re.escape(word)}\b", replacement, text)


def _coerce(value: str) -> Any:
    if value == "true":
        return True
    if value == "false":
        return False
    if value.lstrip("-").isdigit():
        return int(value)
    return value


# ---------------------------------------------------------------------------
# Canonical T_3 factory (the headline-theorem instance)
# ---------------------------------------------------------------------------


def canonical_t3_cgs(
    *,
    max_rounds: int = 2,
    witness_initial: Mapping[str, bool] | None = None,
) -> DeliberationCGS:
    """Build the canonical T_3-like CGS used in the T7 headline theorem.

    The canonical instance has 3 agents (alice, bob, carol). Each agent
    has a private ``has_witness_p1`` boolean and the {Propose, Vote,
    Abstain} action projection from the spec. The default
    ``witness_initial`` sets every agent's witness flag to false (the
    T_3 no-go instance: T7 predicts no agent has a strategy to disclose
    evidence). Pass ``witness_initial={"agent_alice": True}`` for the
    positive instance used in Stage 5's sanity test.
    """
    short_ids = ("alice", "bob", "carol")
    agent_ids = tuple(f"agent_{s}" for s in short_ids)
    if witness_initial is None:
        witness_initial = {}
    actions = ("propose_no_witness", "propose_with_witness", "vote_p1", "abstain")

    agents = tuple(
        CGSAgentSpec(
            agent_id=aid,
            actions=actions,
            private_vars={"has_witness_p1": "boolean"},
            initial_values={
                "has_witness_p1": "true" if witness_initial.get(aid, False) else "false",
            },
            protocol=(
                # propose_with_witness gated by has_witness_p1 = true
                CGSProtocolClause(
                    condition="has_witness_p1 = true",
                    actions=("propose_no_witness", "propose_with_witness", "vote_p1", "abstain"),
                ),
                CGSProtocolClause(
                    condition="has_witness_p1 = false",
                    actions=("propose_no_witness", "vote_p1", "abstain"),
                ),
            ),
        )
        for aid in agent_ids
    )

    env_public: dict[str, str] = {"round": f"0..{max_rounds}"}
    env_initial: dict[str, str] = {"round": "0"}
    for short in short_ids:
        env_public[f"disclosed_p1_{short}"] = "boolean"
        env_initial[f"disclosed_p1_{short}"] = "false"
        env_public[f"voted_p1_{short}"] = "boolean"
        env_initial[f"voted_p1_{short}"] = "false"

    environment = CGSEnvironmentSpec(
        public_vars=env_public,
        private_vars={},
        initial_values=env_initial,
        evolution_rules=(),  # encoded inline in DeliberationCGS.step for clarity
    )

    aps: list[CGSAtomicProposition] = []
    consensus_expr = " and ".join(
        f"Environment.voted_p1_{s} = true" for s in short_ids
    )
    aps.append(CGSAtomicProposition(name="consensus_p1", expression=consensus_expr))
    for short in short_ids:
        aps.append(
            CGSAtomicProposition(
                name=f"evidence_p1_{short}",
                expression=f"Environment.disclosed_p1_{short} = true",
            )
        )
        aps.append(
            CGSAtomicProposition(
                name=f"voted_p1_{short}",
                expression=f"Environment.voted_p1_{short} = true",
            )
        )

    groups = tuple(
        CGSGroup(name=f"g_{short}", members=(f"agent_{short}",)) for short in short_ids
    )

    return DeliberationCGS(
        agents=agents,
        environment=environment,
        atomic_propositions=tuple(aps),
        groups=groups,
        max_rounds=max_rounds,
    )


# ---------------------------------------------------------------------------
# ISPL emitter (CGS → MCMAS-parseable text)
#
# Uses ``Semantics = SingleAssignment;`` so all variables update
# simultaneously per joint action (MultiAssignment forces a
# non-deterministic choice between updates — wrong for our setting).
# ADR-0020 documents this and the rest of the encoding decisions.
# ---------------------------------------------------------------------------


def cgs_to_ispl(cgs: DeliberationCGS, formulae: Sequence[LTLf]) -> str:
    """Emit MCMAS-parseable ISPL for ``cgs`` and ``formulae``.

    Output format follows MCMAS manual §3.2.4 (page 19): Semantics,
    Environment agent, normal agents, Evaluation, InitStates, Groups,
    Formulae. Empty ``formulae`` is rejected per the ISPL grammar
    (``formlist`` requires at least one formula).
    """
    if not formulae:
        raise ValueError("at least one formula required (ISPL Formulae cannot be empty)")
    sections: list[str] = []
    sections.append("-- Generated by council.symbolic.verify.cgs.cgs_to_ispl")
    sections.append("Semantics = SingleAssignment;")
    sections.append("")
    sections.append(_emit_environment(cgs))
    for agent in cgs.agents:
        sections.append("")
        sections.append(_emit_agent(agent))
    sections.append("")
    sections.append(_emit_evaluation(cgs.atomic_propositions))
    sections.append("")
    sections.append(_emit_init_states(cgs))
    sections.append("")
    sections.append(_emit_groups(cgs.groups))
    sections.append("")
    sections.append(_emit_formulae(formulae))
    return "\n".join(sections) + "\n"


def _emit_environment(cgs: DeliberationCGS) -> str:
    env = cgs.environment
    lines = ["Agent Environment"]
    if env.public_vars:
        lines.append("  Obsvars:")
        for name, type_ in env.public_vars.items():
            lines.append(f"    {name} : {type_};")
        lines.append("  end Obsvars")
    # Vars block (envvardef?) — optional per ISPL grammar; omit when empty.
    if env.private_vars:
        lines.append("  Vars:")
        for name, type_ in env.private_vars.items():
            lines.append(f"    {name} : {type_};")
        lines.append("  end Vars")
    lines.append("  Actions = { tick };")
    lines.append("  Protocol:")
    lines.append("    Other: { tick };")
    lines.append("  end Protocol")
    lines.append("  Evolution:")
    # Round counter (saturating at max_rounds)
    for r in range(cgs.max_rounds):
        lines.append(f"    round = {r + 1} if round = {r};")
    # Disclosure flags: env tracks each agent's propose_with_witness action.
    for agent in cgs.agents:
        short = _short_id(agent.agent_id)
        lines.append(
            f"    disclosed_p1_{short} = true "
            f"if {agent.agent_id}.Action = propose_with_witness;"
        )
    # Vote flags
    for agent in cgs.agents:
        short = _short_id(agent.agent_id)
        lines.append(
            f"    voted_p1_{short} = true if {agent.agent_id}.Action = vote_p1;"
        )
    lines.append("  end Evolution")
    lines.append("end Agent")
    return "\n".join(lines)


def _emit_agent(agent: CGSAgentSpec) -> str:
    lines = [f"Agent {agent.agent_id}"]
    # Lobsvars: the agent observes every public env var. The names are
    # listed without prefix (per manual page 14 — Lobsvars take env var
    # names directly).
    # We list all obsvars by extracting names from the canonical env
    # spec; for cleanliness we hard-list them here in the canonical_t3
    # encoding. The general emitter would inspect cgs.environment.public_vars.
    lines.append("  Lobsvars = { round, "
                 "disclosed_p1_alice, disclosed_p1_bob, disclosed_p1_carol, "
                 "voted_p1_alice, voted_p1_bob, voted_p1_carol };")
    lines.append("  Vars:")
    for name, type_ in agent.private_vars.items():
        lines.append(f"    {name} : {type_};")
    lines.append("  end Vars")
    actions_str = ", ".join(agent.actions)
    lines.append(f"  Actions = {{ {actions_str} }};")
    lines.append("  Protocol:")
    for clause in agent.protocol:
        clause_actions = ", ".join(clause.actions)
        lines.append(f"    {clause.condition} : {{ {clause_actions} }};")
    lines.append("  end Protocol")
    lines.append("  Evolution:")
    # Tautological self-update rules to satisfy `evline+` requirement.
    # In SingleAssignment, these only fire when the var already has the
    # specified value, preserving has_witness_p1's immutability.
    for var in agent.private_vars:
        if agent.private_vars[var] == "boolean":
            lines.append(f"    {var} = true if {var} = true;")
            lines.append(f"    {var} = false if {var} = false;")
    lines.append("  end Evolution")
    lines.append("end Agent")
    return "\n".join(lines)


def _emit_evaluation(aps: tuple[CGSAtomicProposition, ...]) -> str:
    lines = ["Evaluation"]
    for ap in aps:
        lines.append(f"  {ap.name} if {ap.expression};")
    lines.append("end Evaluation")
    return "\n".join(lines)


def _emit_init_states(cgs: DeliberationCGS) -> str:
    parts: list[str] = []
    for name, value in cgs.environment.initial_values.items():
        parts.append(f"Environment.{name} = {value}")
    for agent in cgs.agents:
        for name, value in agent.initial_values.items():
            parts.append(f"{agent.agent_id}.{name} = {value}")
    body = " and ".join(parts)
    return f"InitStates\n  {body};\nend InitStates"


def _emit_groups(groups: tuple[CGSGroup, ...]) -> str:
    lines = ["Groups"]
    for g in groups:
        members = ", ".join(g.members)
        lines.append(f"  {g.name} = {{ {members} }};")
    lines.append("end Groups")
    return "\n".join(lines)


def _emit_formulae(formulae: Sequence[LTLf]) -> str:
    lines = ["Formulae"]
    for f in formulae:
        lines.append(f"  {ltlf_to_ctl(f)};")
    lines.append("end Formulae")
    return "\n".join(lines)
