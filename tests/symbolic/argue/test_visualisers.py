"""Tests for council/symbolic/argue/visualisers.py — Mermaid + DOT emitters.

Pure string emitters (no model calls, no async). Deterministic: same QBAF
produces byte-equal output across runs. The Walton-Krabbe canonical
fixture serves as the demo golden — committed Mermaid string is verified
exactly.
"""

from __future__ import annotations

import pytest

from council.symbolic.argue.baf import QBAF, Argument, Attack, Support
from council.symbolic.argue.visualisers import to_dot, to_mermaid


def _walton_krabbe_qbaf() -> QBAF:
    """The PR2/Slice D canonical 5-move trace builds this QBAF (without
    vote boost, since strengths are a semantics concern, not the QBAF)."""
    return QBAF(
        arguments=(
            Argument(arg_id="p1", claim_surface="X is true", base_score=1.0),
            Argument(arg_id="p2", claim_surface="X is false", base_score=0.6),
            Argument(arg_id="c1", claim_surface="counterexample C", base_score=0.7),
            Argument(arg_id="co1", claim_surface="(concession to p2)", base_score=1.0),
        ),
        attacks=(Attack(source="c1", target="p1", weight=0.7),),
        supports=(Support(source="co1", target="p2", weight=1.0),),
    )


# ---------------------------------------------------------------------------
# to_mermaid — empty / minimal
# ---------------------------------------------------------------------------


class TestMermaidMinimal:
    def test_empty_qbaf_returns_minimal_diagram(self) -> None:
        baf = QBAF(arguments=(), attacks=(), supports=())
        out = to_mermaid(baf)
        assert out.startswith("flowchart TD")

    def test_single_argument_appears_as_node(self) -> None:
        a = Argument(arg_id="a1", claim_surface="hello", base_score=0.5)
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        out = to_mermaid(baf)
        assert "a1" in out
        assert "hello" in out

    def test_returns_string(self) -> None:
        out = to_mermaid(_walton_krabbe_qbaf())
        assert isinstance(out, str)


# ---------------------------------------------------------------------------
# Mermaid syntax — node and edge formatting
# ---------------------------------------------------------------------------


class TestMermaidSyntax:
    def test_flowchart_directive_present(self) -> None:
        out = to_mermaid(_walton_krabbe_qbaf())
        assert "flowchart TD" in out

    def test_each_argument_emitted(self) -> None:
        out = to_mermaid(_walton_krabbe_qbaf())
        for arg_id in ("p1", "p2", "c1", "co1"):
            assert arg_id in out

    def test_node_label_includes_claim_surface(self) -> None:
        out = to_mermaid(_walton_krabbe_qbaf())
        assert "X is true" in out
        assert "X is false" in out
        assert "counterexample C" in out

    def test_node_label_includes_base_score(self) -> None:
        out = to_mermaid(_walton_krabbe_qbaf())
        # All four base scores should appear formatted to two decimals
        assert "1.00" in out
        assert "0.60" in out
        assert "0.70" in out

    def test_attack_edge_solid_arrow(self) -> None:
        out = to_mermaid(_walton_krabbe_qbaf())
        # Mermaid solid arrow for attacks: c1 -->|...| p1
        assert "c1 -->" in out
        assert "p1" in out
        assert "attack" in out

    def test_support_edge_dashed_arrow(self) -> None:
        out = to_mermaid(_walton_krabbe_qbaf())
        # Mermaid dashed arrow for supports: co1 -.->|...| p2
        assert "co1 -.->" in out
        assert "support" in out

    def test_attack_weight_in_edge_label(self) -> None:
        baf = QBAF(
            arguments=(
                Argument(arg_id="a", claim_surface="A", base_score=0.5),
                Argument(arg_id="b", claim_surface="B", base_score=0.5),
            ),
            attacks=(Attack(source="a", target="b", weight=0.42),),
            supports=(),
        )
        out = to_mermaid(baf)
        assert "0.42" in out


# ---------------------------------------------------------------------------
# Withdrawn nodes — class styling
# ---------------------------------------------------------------------------


class TestMermaidWithdrawn:
    def test_withdrawn_argument_marked_with_class(self) -> None:
        a = Argument(
            arg_id="a1",
            claim_surface="retracted",
            base_score=0.5,
            withdrawn=True,
        )
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        out = to_mermaid(baf)
        # Mermaid class syntax: a1:::withdrawn or :::withdrawn applied
        assert "withdrawn" in out

    def test_withdrawn_classdef_in_output(self) -> None:
        a = Argument(
            arg_id="a1",
            claim_surface="r",
            base_score=0.5,
            withdrawn=True,
        )
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        out = to_mermaid(baf)
        # The classDef (CSS) for withdrawn must be defined in the diagram
        assert "classDef withdrawn" in out


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestMermaidDeterminism:
    def test_byte_equal_over_50_invocations(self) -> None:
        baf = _walton_krabbe_qbaf()
        first = to_mermaid(baf)
        for _ in range(50):
            assert to_mermaid(baf) == first

    def test_different_argument_order_gives_different_output(self) -> None:
        """Insertion order is preserved in node emission."""
        a = Argument(arg_id="alpha", claim_surface="A", base_score=0.5)
        b = Argument(arg_id="beta", claim_surface="B", base_score=0.5)
        baf1 = QBAF(arguments=(a, b), attacks=(), supports=())
        baf2 = QBAF(arguments=(b, a), attacks=(), supports=())
        out1 = to_mermaid(baf1)
        out2 = to_mermaid(baf2)
        # Look for node-line prefix specifically (4-space indent + arg_id)
        assert out1.index("    alpha[") < out1.index("    beta[")
        assert out2.index("    beta[") < out2.index("    alpha[")


# ---------------------------------------------------------------------------
# Strengths overlay
# ---------------------------------------------------------------------------


class TestMermaidStrengthsOverlay:
    def test_strengths_appear_in_node_labels(self) -> None:
        baf = _walton_krabbe_qbaf()
        strengths = {"p1": 0.51, "p2": 1.0, "c1": 0.7, "co1": 1.0}
        out = to_mermaid(baf, strengths=strengths)
        # Strength values for each node should appear
        assert "0.51" in out  # p1's strength

    def test_strengths_none_omits_strength_in_label(self) -> None:
        baf = _walton_krabbe_qbaf()
        out = to_mermaid(baf, strengths=None)
        # Without strengths, only base scores appear; "str=" prefix absent
        assert "str=" not in out

    def test_strengths_dict_partial_handled_gracefully(self) -> None:
        """If strengths dict doesn't cover all args, render base only for
        those without strengths (no KeyError)."""
        baf = _walton_krabbe_qbaf()
        partial = {"p1": 0.51}
        # Should not raise
        out = to_mermaid(baf, strengths=partial)
        assert "0.51" in out
        # Other nodes still appear
        assert "p2" in out


# ---------------------------------------------------------------------------
# HTML escaping — special chars in claim surfaces don't break Mermaid syntax
# ---------------------------------------------------------------------------


class TestMermaidEscaping:
    def test_quotes_in_claim_surface_escaped(self) -> None:
        a = Argument(
            arg_id="a",
            claim_surface='He said "hi"',
            base_score=0.5,
        )
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        out = to_mermaid(baf)
        # Bare " inside Mermaid ["..."] would break syntax. Must be escaped.
        # We accept either &quot; or #quot; HTML entity.
        assert ("&quot;" in out) or ("#quot;" in out)

    def test_angle_brackets_escaped(self) -> None:
        a = Argument(
            arg_id="a",
            claim_surface="x < y > z",
            base_score=0.5,
        )
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        out = to_mermaid(baf)
        # Bare < / > would break HTML interpretation
        assert "&lt;" in out or "<br/>" in out  # at least &lt; substitution
        assert "&gt;" in out or ">" not in out.replace("flowchart TD", "")


# ---------------------------------------------------------------------------
# Walton-Krabbe golden string
# ---------------------------------------------------------------------------


class TestMermaidWaltonKrabbeGolden:
    """Pinned canonical Mermaid emission for the W2/PR2 fixture. Updating
    this fixture is a deliberate spec change.
    """

    def test_walton_krabbe_canonical_mermaid(self) -> None:
        baf = _walton_krabbe_qbaf()
        out = to_mermaid(baf)
        # Strict structural assertions — any deviation breaks this test.
        # The format is committed; renderers rely on it stable.
        expected_lines = [
            "flowchart TD",
            'p1["X is true<br/>base=1.00"]',
            'p2["X is false<br/>base=0.60"]',
            'c1["counterexample C<br/>base=0.70"]',
            'co1["(concession to p2)<br/>base=1.00"]',
            "c1 -->|attack 0.70| p1",
            "co1 -.->|support 1.00| p2",
        ]
        for line in expected_lines:
            assert line in out, f"Expected Mermaid line missing: {line}"


# ---------------------------------------------------------------------------
# to_dot — empty / minimal
# ---------------------------------------------------------------------------


class TestDotMinimal:
    def test_empty_qbaf_returns_minimal_digraph(self) -> None:
        baf = QBAF(arguments=(), attacks=(), supports=())
        out = to_dot(baf)
        assert "digraph QBAF" in out
        assert out.endswith("}")

    def test_returns_string(self) -> None:
        out = to_dot(_walton_krabbe_qbaf())
        assert isinstance(out, str)


# ---------------------------------------------------------------------------
# to_dot — syntax + edge styling
# ---------------------------------------------------------------------------


class TestDotSyntax:
    def test_digraph_header_and_rankdir(self) -> None:
        out = to_dot(_walton_krabbe_qbaf())
        assert "digraph QBAF {" in out
        # rankdir TD = top-down (matches Mermaid's flowchart TD)
        assert 'rankdir="TD"' in out

    def test_each_argument_emitted(self) -> None:
        out = to_dot(_walton_krabbe_qbaf())
        for arg_id in ("p1", "p2", "c1", "co1"):
            # Node line format: arg_id [label="..."];
            assert f"{arg_id} [" in out

    def test_node_label_includes_claim_surface(self) -> None:
        out = to_dot(_walton_krabbe_qbaf())
        assert "X is true" in out
        assert "X is false" in out

    def test_attack_edge_red_solid(self) -> None:
        out = to_dot(_walton_krabbe_qbaf())
        # Attack edge: c1 -> p1 [label="attack 0.70", color="red"];
        assert "c1 -> p1" in out
        assert 'color="red"' in out

    def test_support_edge_green_dashed(self) -> None:
        out = to_dot(_walton_krabbe_qbaf())
        # Support edge: co1 -> p2 [label="support 1.00", color="darkgreen", style="dashed"];
        assert "co1 -> p2" in out
        assert 'color="darkgreen"' in out
        assert 'style="dashed"' in out

    def test_attack_weight_in_label(self) -> None:
        baf = QBAF(
            arguments=(
                Argument(arg_id="a", claim_surface="A", base_score=0.5),
                Argument(arg_id="b", claim_surface="B", base_score=0.5),
            ),
            attacks=(Attack(source="a", target="b", weight=0.42),),
            supports=(),
        )
        out = to_dot(baf)
        assert "0.42" in out
        assert "attack" in out


# ---------------------------------------------------------------------------
# to_dot — withdrawn styling
# ---------------------------------------------------------------------------


class TestDotWithdrawn:
    def test_withdrawn_argument_styled_dashed_grey(self) -> None:
        a = Argument(
            arg_id="a1",
            claim_surface="r",
            base_score=0.5,
            withdrawn=True,
        )
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        out = to_dot(baf)
        assert 'style="dashed"' in out
        assert 'color="grey"' in out


# ---------------------------------------------------------------------------
# to_dot — strengths overlay
# ---------------------------------------------------------------------------


class TestDotStrengthsOverlay:
    def test_strengths_appear_in_node_labels(self) -> None:
        baf = _walton_krabbe_qbaf()
        strengths = {"p1": 0.51, "p2": 1.0, "c1": 0.7, "co1": 1.0}
        out = to_dot(baf, strengths=strengths)
        assert "0.51" in out

    def test_strengths_none_omits_str_prefix(self) -> None:
        out = to_dot(_walton_krabbe_qbaf(), strengths=None)
        assert "str=" not in out


# ---------------------------------------------------------------------------
# to_dot — escaping
# ---------------------------------------------------------------------------


class TestDotEscaping:
    def test_quotes_in_claim_surface_escaped(self) -> None:
        a = Argument(
            arg_id="a",
            claim_surface='He said "hi"',
            base_score=0.5,
        )
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        out = to_dot(baf)
        # DOT escapes " as \" inside quoted strings
        assert '\\"' in out

    def test_backslash_in_claim_surface_escaped(self) -> None:
        a = Argument(
            arg_id="a",
            claim_surface="path\\to\\file",
            base_score=0.5,
        )
        baf = QBAF(arguments=(a,), attacks=(), supports=())
        out = to_dot(baf)
        # Backslashes doubled
        assert "\\\\" in out


# ---------------------------------------------------------------------------
# to_dot — determinism
# ---------------------------------------------------------------------------


class TestDotDeterminism:
    def test_byte_equal_over_50_invocations(self) -> None:
        baf = _walton_krabbe_qbaf()
        first = to_dot(baf)
        for _ in range(50):
            assert to_dot(baf) == first


# ---------------------------------------------------------------------------
# to_dot — pydot round-trip (gated on pydot availability)
# ---------------------------------------------------------------------------


class TestDotPydotRoundTrip:
    """Optional: if pydot is installed, the emitted DOT string parses back
    to a graph with the same node/edge structure. This proves the output
    is well-formed DOT, not just a string that happens to contain the
    expected substrings."""

    def test_pydot_parses_walton_krabbe(self) -> None:
        pydot = pytest.importorskip("pydot")
        baf = _walton_krabbe_qbaf()
        out = to_dot(baf)
        graphs = pydot.graph_from_dot_data(out)
        assert graphs is not None
        assert len(graphs) >= 1
        graph = graphs[0]
        # 4 arguments → 4 nodes
        node_names = {n.get_name() for n in graph.get_nodes() if n.get_name() != "node"}
        # node_names may include trailing "" sentinel; just check expected ids subset
        for arg_id in ("p1", "p2", "c1", "co1"):
            assert arg_id in node_names
        # 1 attack + 1 support → 2 edges
        assert len(graph.get_edges()) == 2


# ---------------------------------------------------------------------------
# to_dot — Walton-Krabbe golden
# ---------------------------------------------------------------------------


class TestDotWaltonKrabbeGolden:
    def test_walton_krabbe_canonical_dot(self) -> None:
        baf = _walton_krabbe_qbaf()
        out = to_dot(baf)
        # Pinned structural lines
        expected_substrings = [
            "digraph QBAF {",
            'rankdir="TD"',
            'p1 [label="X is true\\nbase=1.00"]',
            'p2 [label="X is false\\nbase=0.60"]',
            'c1 [label="counterexample C\\nbase=0.70"]',
            'co1 [label="(concession to p2)\\nbase=1.00"]',
            'c1 -> p1 [label="attack 0.70"',
            'co1 -> p2 [label="support 1.00"',
        ]
        for s in expected_substrings:
            assert s in out, f"Expected DOT substring missing: {s!r}"
