"""L2 argumentation — Mermaid + DOT exporters.

Pure string emitters. No model calls. No async. Deterministic: same QBAF
produces byte-equal output across runs.

The bible §6.3 calls these "the demo gold" — every CouncilResponse from
the headline pipeline carries a Mermaid string in
`AggregationResult.metadata["baf_mermaid"]` so the Streamlit demo (W7)
can live-render the argument graph with strengths overlaid.

Free-function design (matches W1's `trace_to_ispl` / `trace_to_smv`
pattern; ADR-0009 §"to_mermaid not on QBAF" rationale):

    to_mermaid(qbaf, strengths=None) -> str
    to_dot(qbaf, strengths=None) -> str

The optional `strengths: dict[str, float] | None` overlay is the most
common demo-rendering use case: the Aggregator (PR6) computes strengths
via the chosen GradualSemantics and threads them into the visualiser
metadata. Without strengths, only base scores appear in node labels.

Edge styling:
  - Attacks: solid arrows (Mermaid: `-->|attack w|`; DOT: `[label=...]`).
  - Supports: dashed arrows (Mermaid: `-.->|support w|`; DOT:
    `[style=dashed, ...]`).
  - Withdrawn arguments: `:::withdrawn` class (Mermaid) or `style=dotted`
    (DOT). A classDef / node-attribute clause defines the dimmed style.

HTML escaping for Mermaid node labels:
  Mermaid's `id["text"]` syntax requires HTML-escaped special chars:
  `"` -> `&quot;`, `<` -> `&lt;`, `>` -> `&gt;`, `&` -> `&amp;`. Newlines
  in claim_surface are converted to `<br/>` (Mermaid-compatible).

Determinism: insertion order is preserved for both arguments and edges
to ensure byte-equal output. The QBAF's tuple-of-tuples structure is
already deterministic.
"""

from __future__ import annotations

from council.symbolic.argue.baf import QBAF


def _escape_mermaid_label(text: str) -> str:
    """HTML-escape a string for safe inclusion inside Mermaid `id["text"]`."""
    # Order matters: & must be escaped first, otherwise we'd double-escape
    # the entities we just inserted.
    text = text.replace("&", "&amp;")
    text = text.replace('"', "&quot;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace("\n", "<br/>")
    return text


def _escape_dot_label(text: str) -> str:
    """Escape a string for safe inclusion inside DOT `[label="..."]`."""
    text = text.replace("\\", "\\\\")
    text = text.replace('"', '\\"')
    text = text.replace("\n", "\\n")
    return text


def to_mermaid(
    qbaf: QBAF,
    *,
    strengths: dict[str, float] | None = None,
) -> str:
    """Render a QBAF as a Mermaid `flowchart TD` diagram.

    Args:
        qbaf: the QBAF to render.
        strengths: optional dict[arg_id, strength] overlay. When given,
            each node label appends `, str=X.XX`. When None, only the
            base score appears.

    Returns a deterministic string suitable for embedding in Markdown,
    HTML, or the Streamlit demo's `st.markdown(... ,unsafe_allow_html=True)`.
    """
    lines: list[str] = ["flowchart TD"]

    # Nodes
    for arg in qbaf.arguments:
        label_parts = [_escape_mermaid_label(arg.claim_surface)]
        label_parts.append(f"base={arg.base_score:.2f}")
        if strengths is not None and arg.arg_id in strengths:
            label_parts.append(f"str={strengths[arg.arg_id]:.2f}")
        label = "<br/>".join(label_parts)
        node = f'    {arg.arg_id}["{label}"]'
        if arg.withdrawn:
            node = f"{node}:::withdrawn"
        lines.append(node)

    # Attack edges (solid arrows)
    for att in qbaf.attacks:
        lines.append(
            f"    {att.source} -->|attack {att.weight:.2f}| {att.target}"
        )

    # Support edges (dashed arrows)
    for sup in qbaf.supports:
        lines.append(
            f"    {sup.source} -.->|support {sup.weight:.2f}| {sup.target}"
        )

    # Withdrawn class style — emitted unconditionally so the diagram is
    # self-contained even when no withdrawn arguments are present
    lines.append("    classDef withdrawn stroke-dasharray:5 5,opacity:0.5")

    return "\n".join(lines)


def to_dot(
    qbaf: QBAF,
    *,
    strengths: dict[str, float] | None = None,
) -> str:
    """Render a QBAF as a Graphviz DOT digraph.

    Same overlay semantics as `to_mermaid`. Suitable for `graphviz` /
    `pydot` / `dot -Tpng` rendering.
    """
    lines: list[str] = ["digraph QBAF {", '    rankdir="TD";']

    # Nodes
    for arg in qbaf.arguments:
        label_parts = [_escape_dot_label(arg.claim_surface)]
        label_parts.append(f"base={arg.base_score:.2f}")
        if strengths is not None and arg.arg_id in strengths:
            label_parts.append(f"str={strengths[arg.arg_id]:.2f}")
        label = "\\n".join(label_parts)
        attrs = [f'label="{label}"']
        if arg.withdrawn:
            attrs.append('style="dashed"')
            attrs.append('color="grey"')
        lines.append(f'    {arg.arg_id} [{", ".join(attrs)}];')

    # Attack edges
    for att in qbaf.attacks:
        lines.append(
            f'    {att.source} -> {att.target} '
            f'[label="attack {att.weight:.2f}", color="red"];'
        )

    # Support edges
    for sup in qbaf.supports:
        lines.append(
            f'    {sup.source} -> {sup.target} '
            f'[label="support {sup.weight:.2f}", color="darkgreen", style="dashed"];'
        )

    lines.append("}")
    return "\n".join(lines)
