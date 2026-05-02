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

from collections.abc import Callable, Mapping, Sequence
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
    """Specification of one council agent in the CGS.

    ``lobsvars`` is the agent's per-agent observability opt-in into
    *private* env vars (``Environment.Vars``). Public env vars
    (``Environment.Obsvars``) are observable by every agent without
    being listed here (MCMAS manual page 14). For the canonical
    ``canonical_t3_cgs`` encoding ``lobsvars`` is empty, because every
    relevant deliberation variable is in ``Environment.Obsvars``.
    Future encodings that introduce moderator-private state (e.g.,
    intervention-counter visible only to a subset of agents) populate
    ``lobsvars`` per agent.
    """

    agent_id: str
    actions: tuple[str, ...]
    private_vars: Mapping[str, str]  # var_name → ISPL type ("boolean", "0..3", ...)
    initial_values: Mapping[str, str]  # var_name → ISPL value
    protocol: tuple[CGSProtocolClause, ...]
    lobsvars: tuple[str, ...] = ()

    def __hash__(self) -> int:
        return hash((
            self.agent_id,
            self.actions,
            tuple(sorted(self.private_vars.items())),
            tuple(sorted(self.initial_values.items())),
            self.protocol,
            self.lobsvars,
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

    Pure recursive-descent tokenizer + parser; no ``eval()``. Grammar
    of the supported subset:

        expr           := or_expr
        or_expr        := and_expr ('or' and_expr)*
        and_expr       := unary_expr ('and' unary_expr)*
        unary_expr     := ('!' | 'not') unary_expr | primary_expr
        primary_expr   := comparison | '(' expr ')'
        comparison     := qualified_name '=' (qualified_name | literal)
        qualified_name := IDENT ('.' IDENT)?
        literal        := 'true' | 'false' | NUMBER

    Names resolve in this priority: ``Scope.var`` looks up
    ``full_state[Scope][var]`` first, then ``public_env[var]`` for
    ``Environment.var``; bare ``var`` looks up ``local_vars`` first,
    then any scope in ``full_state``. Unknown names raise
    ``ValueError``.
    """

    def lookup(name: str) -> Any:
        if "." in name:
            scope, var = name.split(".", 1)
            if full_state is not None and scope in full_state and var in full_state[scope]:
                return _coerce(full_state[scope][var])
            if scope == "Environment" and var in public_env:
                return _coerce(public_env[var])
            raise ValueError(f"unknown qualified name {name!r}")
        if name in local_vars:
            return _coerce(local_vars[name])
        if full_state is not None:
            for scope_vars in full_state.values():
                if name in scope_vars:
                    return _coerce(scope_vars[name])
        raise ValueError(f"unknown name {name!r}")

    try:
        tokens = _tokenize(expression)
        result, consumed = _parse_or(tokens, 0, lookup)
        if consumed != len(tokens):
            raise ValueError(
                f"unexpected trailing tokens after position {consumed}"
            )
        return bool(result)
    except ValueError as exc:
        raise ValueError(
            f"unable to evaluate ISPL condition {expression!r}: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Tokenizer + recursive-descent parser for the ISPL Boolean subset
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str  # see _tokenize for the kind enumeration
    value: str


def _tokenize(text: str) -> list[_Token]:
    """ISPL Boolean tokenizer; raises ValueError on illegal characters."""
    tokens: list[_Token] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c == "(":
            tokens.append(_Token("LPAREN", c))
            i += 1
        elif c == ")":
            tokens.append(_Token("RPAREN", c))
            i += 1
        elif c == "=":
            tokens.append(_Token("EQ", c))
            i += 1
        elif c == "!":
            tokens.append(_Token("NOT", c))
            i += 1
        elif c == ".":
            tokens.append(_Token("DOT", c))
            i += 1
        elif c.isalpha() or c == "_":
            j = i
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            word = text[i:j]
            keywords = {
                "and": "AND",
                "or": "OR",
                "not": "NOT",
                "true": "TRUE",
                "false": "FALSE",
            }
            tokens.append(_Token(keywords.get(word, "IDENT"), word))
            i = j
        elif c.isdigit() or (c == "-" and i + 1 < n and text[i + 1].isdigit()):
            j = i + 1
            while j < n and text[j].isdigit():
                j += 1
            tokens.append(_Token("NUMBER", text[i:j]))
            i = j
        else:
            raise ValueError(f"illegal character {c!r} at position {i}")
    return tokens


def _parse_or(tokens: list[_Token], pos: int, lookup: Callable[[str], Any]) -> tuple[bool, int]:
    left, pos = _parse_and(tokens, pos, lookup)
    while pos < len(tokens) and tokens[pos].kind == "OR":
        right, pos = _parse_and(tokens, pos + 1, lookup)
        left = left or right
    return left, pos


def _parse_and(tokens: list[_Token], pos: int, lookup: Callable[[str], Any]) -> tuple[bool, int]:
    left, pos = _parse_unary(tokens, pos, lookup)
    while pos < len(tokens) and tokens[pos].kind == "AND":
        right, pos = _parse_unary(tokens, pos + 1, lookup)
        left = left and right
    return left, pos


def _parse_unary(tokens: list[_Token], pos: int, lookup: Callable[[str], Any]) -> tuple[bool, int]:
    if pos < len(tokens) and tokens[pos].kind == "NOT":
        inner, pos = _parse_unary(tokens, pos + 1, lookup)
        return (not inner), pos
    return _parse_primary(tokens, pos, lookup)


def _parse_primary(tokens: list[_Token], pos: int, lookup: Callable[[str], Any]) -> tuple[bool, int]:
    if pos < len(tokens) and tokens[pos].kind == "LPAREN":
        result, pos = _parse_or(tokens, pos + 1, lookup)
        if pos >= len(tokens) or tokens[pos].kind != "RPAREN":
            raise ValueError("expected ')' to close parenthesised expression")
        return result, pos + 1
    return _parse_comparison(tokens, pos, lookup)


def _parse_comparison(tokens: list[_Token], pos: int, lookup: Callable[[str], Any]) -> tuple[bool, int]:
    lhs, pos = _parse_qualified(tokens, pos)
    if pos >= len(tokens) or tokens[pos].kind != "EQ":
        raise ValueError(
            f"expected '=' after {lhs!r} at position {pos}, "
            f"got {tokens[pos] if pos < len(tokens) else 'EOF'}"
        )
    pos += 1
    if pos >= len(tokens):
        raise ValueError("unexpected end of expression after '='")
    rhs_tok = tokens[pos]
    if rhs_tok.kind == "TRUE":
        rhs_val: Any = True
        pos += 1
    elif rhs_tok.kind == "FALSE":
        rhs_val = False
        pos += 1
    elif rhs_tok.kind == "NUMBER":
        rhs_val = int(rhs_tok.value)
        pos += 1
    elif rhs_tok.kind == "IDENT":
        rhs_qualified, pos = _parse_qualified(tokens, pos)
        rhs_val = lookup(rhs_qualified)
    else:
        raise ValueError(f"unexpected RHS token kind {rhs_tok.kind!r} ({rhs_tok.value!r})")
    return lookup(lhs) == rhs_val, pos


def _parse_qualified(tokens: list[_Token], pos: int) -> tuple[str, int]:
    if pos >= len(tokens) or tokens[pos].kind != "IDENT":
        raise ValueError(
            f"expected identifier at position {pos}, "
            f"got {tokens[pos] if pos < len(tokens) else 'EOF'}"
        )
    first = tokens[pos].value
    pos += 1
    if pos < len(tokens) and tokens[pos].kind == "DOT":
        pos += 1
        if pos >= len(tokens) or tokens[pos].kind != "IDENT":
            raise ValueError(
                f"expected identifier after '.' at position {pos}"
            )
        return f"{first}.{tokens[pos].value}", pos + 1
    return first, pos


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
        sections.append(_emit_agent(agent, cgs.environment))
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


def _emit_agent(agent: CGSAgentSpec, environment: CGSEnvironmentSpec) -> str:
    # Lobsvars validation (MCMAS manual page 14): the section is the
    # agent's per-agent opt-in into Environment.Vars (private env state).
    # Public env state lives in Environment.Obsvars and is observable by
    # all agents *without* being listed in any Lobsvars; MCMAS rejects
    # such listings with "local observable variable X is not defined in
    # the environment" (see the Stage 5.3 commit `5f178a4` that
    # discovered this). The validation here turns a future silent bug
    # ("env has private state but no Lobsvars wires it up") into a loud
    # construction-time error.
    for name in agent.lobsvars:
        if name not in environment.private_vars:
            raise ValueError(
                f"agent {agent.agent_id!r} Lobsvars references "
                f"{name!r}, which is not in Environment.private_vars "
                f"(env.private_vars keys: "
                f"{sorted(environment.private_vars)}). Public env vars "
                f"in Environment.Obsvars are observable by every agent "
                f"by default and must NOT appear in any agent's Lobsvars."
            )

    lines = [f"Agent {agent.agent_id}"]
    if agent.lobsvars:
        members = ", ".join(agent.lobsvars)
        lines.append(f"  Lobsvars = {{ {members} }};")
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
