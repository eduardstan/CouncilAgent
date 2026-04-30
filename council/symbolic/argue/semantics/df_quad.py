"""DF-QuAD gradual semantics -- Rago, Toni, Aurisicchio, Baroni (KR 2016).

`papers/3 --- argumentation/Rago et al. 2016 ... (KR).pdf` defines DF-QuAD on
acyclic QuAD frameworks with unweighted attack/support relations. The W2
generalisation (ADR-0010) extends this to:

  - Weighted edges: each edge contributes `weight * strength(source)`.
  - Withdrawn arguments: strength = 0 in the result; contribute 0 to all
    aggregations (ADR-0010 Q2).
  - Cycle detection: raise ValueError on cyclic graphs (ADR-0010 Q3); PR4
    (Quadratic Energy semantics, Potyka 2018) handles cycles via continuous
    dynamics.
  - Preferred extension: non-withdrawn arguments with strength >= 0.5
    (ADR-0010 Q4).

Algorithm:
  1. Topological sort over (attacks union supports) edges. Raise on cycle.
  2. For each argument in topological order (sources before sinks):
     - if withdrawn: strength = 0
     - else: gather attacker contributions = [att.weight * strength(att.source)
       for att in incoming_attacks]; same for supporters
     - v_a = F(attacker_contributions); v_s = F(supporter_contributions)
     - strength = c(base_score, v_a, v_s)

F closed form (Lemma 1): F(v_1, ..., v_n) = 1 - prod_{i=1}^n (1 - v_i)
c (Equations 19, 20):
  c(v_0, v_a, v_s) = v_0 - v_0 * |v_s - v_a|        if v_a >= v_s
                   = v_0 + (1 - v_0) * |v_s - v_a|  if v_a < v_s
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from council.symbolic.argue.baf import QBAF, Argument
from council.symbolic.argue.semantics.base import GradualSemantics

#: Preferred-extension threshold. ADR-0010 Q4 — non-withdrawn arguments at or
#: above this strength are members of the preferred extension.
_EXTENSION_THRESHOLD = 0.5


def _f_aggregate(values: Iterable[float]) -> float:
    """F(S) = 1 - prod(1 - v_i). Closed form (Lemma 1, Rago 2016)."""
    product = 1.0
    for v in values:
        product *= 1.0 - v
    return 1.0 - product


def _combine(v0: float, v_a: float, v_s: float) -> float:
    """Combination function c (Equations 19, 20, Rago 2016)."""
    if v_a >= v_s:
        return v0 - v0 * abs(v_s - v_a)
    return v0 + (1.0 - v0) * abs(v_s - v_a)


def _topological_order(baf: QBAF) -> list[str]:
    """Kahn's algorithm over (attacks U supports). Sources come before sinks.

    Raises ValueError on cycle (ADR-0010 Q3).
    """
    # Build an indegree map and adjacency (source -> targets).
    indegree: dict[str, int] = {a.arg_id: 0 for a in baf.arguments}
    out_adj: dict[str, list[str]] = defaultdict(list)
    for att in baf.attacks:
        out_adj[att.source].append(att.target)
        indegree[att.target] += 1
    for sup in baf.supports:
        out_adj[sup.source].append(sup.target)
        indegree[sup.target] += 1

    # Process in deterministic order — preserve baf.arguments insertion order.
    order_index = {a.arg_id: i for i, a in enumerate(baf.arguments)}
    queue = sorted(
        (arg_id for arg_id, deg in indegree.items() if deg == 0),
        key=lambda x: order_index[x],
    )
    result: list[str] = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        new_zero = []
        for tgt in out_adj[node]:
            indegree[tgt] -= 1
            if indegree[tgt] == 0:
                new_zero.append(tgt)
        for tgt in sorted(new_zero, key=lambda x: order_index[x]):
            queue.append(tgt)

    if len(result) != len(baf.arguments):
        unresolved = sorted(
            arg_id for arg_id, deg in indegree.items() if deg > 0
        )
        raise ValueError(
            f"DF-QuAD requires an acyclic QBAF; "
            f"cycle detected through {unresolved!r}"
        )
    return result


class DFQuADSemantics(GradualSemantics):
    """Discontinuity-Free Quantitative Argumentation Debate semantics.

    Generalisation of Rago 2016 to weighted edges + withdrawn arguments
    per ADR-0010. On unweighted edges and no withdrawals, reduces to the
    paper algorithm exactly.
    """

    def evaluate(self, baf: QBAF) -> dict[str, float]:
        """Compute per-argument strength dict."""
        if not baf.arguments:
            return {}

        order = _topological_order(baf)
        arg_by_id: dict[str, Argument] = {a.arg_id: a for a in baf.arguments}

        # Group incoming edges by target.
        incoming_attacks: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for att in baf.attacks:
            incoming_attacks[att.target].append((att.source, att.weight))
        incoming_supports: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for sup in baf.supports:
            incoming_supports[sup.target].append((sup.source, sup.weight))

        strengths: dict[str, float] = {}
        for arg_id in order:
            arg = arg_by_id[arg_id]
            if arg.withdrawn:
                strengths[arg_id] = 0.0
                continue

            attacker_contribs = [
                weight * strengths[src]
                for src, weight in incoming_attacks[arg_id]
            ]
            supporter_contribs = [
                weight * strengths[src]
                for src, weight in incoming_supports[arg_id]
            ]
            v_a = _f_aggregate(attacker_contribs)
            v_s = _f_aggregate(supporter_contribs)
            strengths[arg_id] = _combine(arg.base_score, v_a, v_s)

        return strengths

    def preferred_extension(self, baf: QBAF) -> frozenset[str]:
        """Non-withdrawn arguments with strength >= 0.5 (ADR-0010 Q4)."""
        if not baf.arguments:
            return frozenset()
        strengths = self.evaluate(baf)
        return frozenset(
            a.arg_id
            for a in baf.arguments
            if not a.withdrawn and strengths[a.arg_id] >= _EXTENSION_THRESHOLD
        )
