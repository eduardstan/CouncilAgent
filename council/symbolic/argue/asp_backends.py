"""L2 argumentation — ASP-backed extension semantics (Dung 1995).

ADR-0014 records the design. Three classical Dung extension semantics:

  - `grounded_extension(qbaf)` -> frozenset[str]
        Pure-Python fixed-point iteration of the Dung characteristic
        function. Always available (no clingo required).

  - `preferred_extensions(qbaf)` -> frozenset[frozenset[str]]
        Maximal admissible extensions. Computed via clingo's stable-model
        enumeration (Egly-Gaggl-Woltran 2010 "Aspartix" encoding).
        Requires the `[argue-asp]` extra.

  - `stable_extensions(qbaf)` -> frozenset[frozenset[str]]
        Conflict-free sets attacking every non-member. Computed via
        clingo. Requires the `[argue-asp]` extra. May be empty (no stable
        extension exists for some AAFs).

Per ADR-0014 Q2, all three operate on the **attack subgraph only** —
supports do not affect extension membership. Per ADR-0014 Q3, withdrawn
arguments are excluded.

The clingo dependency is import-guarded: the module is import-safe even
without clingo, but `preferred_extensions` and `stable_extensions` raise
`ImportError` at call time when clingo is missing. The W1 verify spot
backend uses the same pattern.
"""

from __future__ import annotations

from collections import defaultdict

from council.symbolic.argue.baf import QBAF

# Import-guard pattern (matches W1 spot_backend.py).
try:
    import clingo as _clingo  # noqa: F401 — exposed via _CLINGO_AVAILABLE
    _CLINGO_AVAILABLE = True
except ImportError:
    _CLINGO_AVAILABLE = False


def _attack_only(qbaf: QBAF) -> tuple[frozenset[str], dict[str, set[str]]]:
    """Project the QBAF to its attack subgraph for non-withdrawn args.

    Returns:
      (args, attackers): args is the set of non-withdrawn arg_ids;
      attackers[arg_id] is the set of (non-withdrawn) attackers of arg_id.
    """
    args = frozenset(a.arg_id for a in qbaf.arguments if not a.withdrawn)
    attackers: dict[str, set[str]] = defaultdict(set)
    for att in qbaf.attacks:
        if att.source in args and att.target in args:
            attackers[att.target].add(att.source)
    return args, attackers


# ---------------------------------------------------------------------------
# Grounded extension — pure-Python fixed point
# ---------------------------------------------------------------------------


def grounded_extension(qbaf: QBAF) -> frozenset[str]:
    """Compute the unique grounded extension via Dung's characteristic function.

    F(S) = { a in args : every attacker of a is attacked by some member of S }.
    Iterate from the empty set; the least fixed point is the grounded
    extension. Termination is guaranteed: F is monotone on a finite lattice.
    """
    args, attackers = _attack_only(qbaf)
    if not args:
        return frozenset()

    grounded: set[str] = set()
    while True:
        new_in = {
            a
            for a in args
            if a not in grounded
            and all(
                any(c in grounded for c in attackers.get(b, set()))
                for b in attackers[a]
            )
        }
        if not new_in:
            break
        grounded |= new_in
    return frozenset(grounded)


# ---------------------------------------------------------------------------
# ASP encoding helper (Egly-Gaggl-Woltran "Aspartix" style; Dung 1995 §3)
# ---------------------------------------------------------------------------


def _encode_aaf(args: frozenset[str], attackers: dict[str, set[str]]) -> str:
    """Encode the AAF as ASP facts: arg(X)., att(X, Y)."""
    lines: list[str] = []
    for a in sorted(args):
        lines.append(f"arg({a}).")
    edges: list[tuple[str, str]] = []
    for target, srcs in attackers.items():
        for src in srcs:
            edges.append((src, target))
    for src, target in sorted(edges):
        lines.append(f"att({src}, {target}).")
    return "\n".join(lines)


def _solve_models(program: str) -> list[frozenset[str]]:
    """Run clingo on the given program and collect `in/1` answer sets.

    Each answer set's `in(X).` facts become one frozenset of strings.
    Raises ImportError when clingo is missing.
    """
    if not _CLINGO_AVAILABLE:
        raise ImportError(
            "clingo is required for ASP-backed extensions. "
            "Install with: pip install 'councilagent[argue-asp]'"
        )
    import clingo

    ctl = clingo.Control(["0"])  # "0" = enumerate all models
    ctl.add("base", [], program)
    ctl.ground([("base", [])])
    models: list[frozenset[str]] = []

    def _on_model(model: clingo.Model) -> None:
        ext = frozenset(
            str(s.arguments[0])
            for s in model.symbols(atoms=True)
            if s.name == "in" and len(s.arguments) == 1
        )
        models.append(ext)

    ctl.solve(on_model=_on_model)
    return models


# ---------------------------------------------------------------------------
# Preferred extensions — admissible + maximal
# ---------------------------------------------------------------------------


_ADMISSIBLE_PROGRAM = """
% Admissible extension encoding (Egly-Gaggl-Woltran 2010 / Aspartix)
% Choice rule: each argument is in or out
{ in(X) } :- arg(X).
% Conflict-free: no in arg attacks another in arg
:- in(X), in(Y), att(X, Y).
% Defended: every attacker of an in arg must be attacked by some in arg
defeated(X) :- in(Y), att(Y, X).
:- in(X), att(Y, X), not defeated(Y).
"""


def preferred_extensions(qbaf: QBAF) -> frozenset[frozenset[str]]:
    """Compute all preferred (maximal admissible) extensions.

    Returns frozenset[frozenset[str]]. The empty set is admissible in every
    AAF; for an empty AAF, returns frozenset({frozenset()}).
    """
    args, attackers = _attack_only(qbaf)
    if not args:
        return frozenset({frozenset()})

    program = _encode_aaf(args, attackers) + "\n" + _ADMISSIBLE_PROGRAM
    admissible = _solve_models(program)

    # Filter to maximal: drop any extension that's a strict subset of another
    maximal: list[frozenset[str]] = []
    for ext in admissible:
        if not any(ext < other for other in admissible):
            maximal.append(ext)

    return frozenset(maximal)


# ---------------------------------------------------------------------------
# Stable extensions — conflict-free + attack every non-member
# ---------------------------------------------------------------------------


_STABLE_PROGRAM = """
% Stable extension encoding (Egly-Gaggl-Woltran 2010 / Aspartix)
{ in(X) } :- arg(X).
% Conflict-free
:- in(X), in(Y), att(X, Y).
% Stable: every non-in argument must be attacked by some in argument
defeated(X) :- in(Y), att(Y, X).
:- arg(X), not in(X), not defeated(X).
"""


def stable_extensions(qbaf: QBAF) -> frozenset[frozenset[str]]:
    """Compute all stable extensions (conflict-free + attack every non-member).

    Returns frozenset[frozenset[str]]. May be empty if no stable extension
    exists (e.g., an odd-length attack cycle).
    """
    args, attackers = _attack_only(qbaf)
    if not args:
        return frozenset({frozenset()})

    program = _encode_aaf(args, attackers) + "\n" + _STABLE_PROGRAM
    return frozenset(_solve_models(program))
