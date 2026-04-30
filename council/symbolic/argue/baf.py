"""L2 argumentation — frozen QBAF dataclasses.

The QBAF (Quantitative Bipolar Argumentation Framework) is the data structure
the L2 aggregator (W2) operates on. It is built deterministically from a typed
Trace by `council.symbolic.argue.builders.build_qbaf` (W2/PR2). Gradual
semantics in `council.symbolic.argue.semantics.*` (W2/PR3-PR5) consume a QBAF
and produce per-argument strength scores.

Design invariants:
  - Every value object is `frozen=True, slots=True`. The QBAF is a value, not
    an entity — building a new QBAF returns a new instance.
  - `Argument.arg_id` equals the originating `Propose.move_id` when produced
    by `build_qbaf`. The constructive invariant is enforced in PR2; this
    module only exposes the field and trusts callers.
  - `Attack.weight` and `Support.weight` are clamped to [0, 1] in
    `__post_init__` (silent clamp, not raise — matches the calibrator-fallback
    model where missing/bad data degrades to neutral, not crash).
  - `QBAF.__post_init__` enforces no self-loops, no dangling edges, and no
    duplicate `arg_id`s. Failures raise `ValueError` on construction.

Visualisation (`to_mermaid`, `to_dot`) is intentionally NOT a method on QBAF —
those live as free functions in `council.symbolic.argue.visualisers` (W2/PR7),
matching the W1 pattern where ISPL/SMV emitters are free functions
(`trace_to_ispl`, `trace_to_smv`), not methods on Trace.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Argument:
    """A node in the QBAF, derived from a Propose move.

    `arg_id` equals the originating Propose's `move_id` when the QBAF is built
    by `build_qbaf` (W2/PR2). Preserves trace-to-graph traceability for the
    ProvenanceReceipt (Constitution §11).
    """

    arg_id: str
    claim_surface: str
    base_score: float
    withdrawn: bool = False


@dataclass(frozen=True, slots=True)
class Attack:
    """Directed attack edge: source attacks target. Weight clamped to [0, 1]."""

    source: str
    target: str
    weight: float

    def __post_init__(self) -> None:
        clamped = max(0.0, min(1.0, self.weight))
        if clamped != self.weight:
            object.__setattr__(self, "weight", clamped)


@dataclass(frozen=True, slots=True)
class Support:
    """Directed support edge: source supports target. Weight clamped to [0, 1]."""

    source: str
    target: str
    weight: float = 1.0

    def __post_init__(self) -> None:
        clamped = max(0.0, min(1.0, self.weight))
        if clamped != self.weight:
            object.__setattr__(self, "weight", clamped)


@dataclass(frozen=True, slots=True)
class QBAF:
    """Quantitative Bipolar Argumentation Framework.

    Validates structural invariants on construction:
      - no duplicate `arg_id`s
      - no self-loops in attacks or supports
      - all attack/support endpoints reference a declared argument

    Failures raise `ValueError`. Validation is one O(V + E) pass.
    """

    arguments: tuple[Argument, ...]
    attacks: tuple[Attack, ...]
    supports: tuple[Support, ...]

    def __post_init__(self) -> None:
        ids: set[str] = set()
        for arg in self.arguments:
            if arg.arg_id in ids:
                raise ValueError(f"duplicate argument id: {arg.arg_id!r}")
            ids.add(arg.arg_id)

        for edge in self.attacks:
            if edge.source == edge.target:
                raise ValueError(f"self-loop in attack: {edge.source!r}")
            if edge.source not in ids:
                raise ValueError(f"attack references unknown argument: {edge.source!r}")
            if edge.target not in ids:
                raise ValueError(f"attack references unknown argument: {edge.target!r}")

        for sedge in self.supports:
            if sedge.source == sedge.target:
                raise ValueError(f"self-loop in support: {sedge.source!r}")
            if sedge.source not in ids:
                raise ValueError(
                    f"support references unknown argument: {sedge.source!r}"
                )
            if sedge.target not in ids:
                raise ValueError(
                    f"support references unknown argument: {sedge.target!r}"
                )

    def proposals(self) -> tuple[Argument, ...]:
        """Non-withdrawn arguments — the candidate winners. Insertion order preserved."""
        return tuple(a for a in self.arguments if not a.withdrawn)
