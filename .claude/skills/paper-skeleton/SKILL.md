---
name: paper-skeleton
description: Generates a P<n> LaTeX skeleton (sections from COUNCILAGENT_NS_MASTER_PLAN.md §9, theorem placeholders from COUNCIL_NS_PLAN.md §10) under papers_drafts/p<n>_<slug>/. Use at paper kickoff time. Scriptable counterpart of the paper-drafter agent.
---

# paper-skeleton

Generate a publication-ready LaTeX skeleton for paper P1, P2, P3, P4, P5, or F.

## Inputs
- `<paper_id>` — `P1` | `P2` | `P3` | `P4` | `P5` | `F`.
- `<slug>` — short kebab slug, e.g. `verified-deliberation`, `qd-deliberation`.

## Procedure

1. **Look up the paper** in `COUNCILAGENT_NS_MASTER_PLAN.md` §9: extract title, layers, theorems, headline empirics, target venue.
2. **Create directory** `papers_drafts/<paper_id>_<slug>/`.
3. **Generate `main.tex`:**
   - Title page (canonical title from §9; authors from `CITATION.cff`).
   - Abstract — locked tagline from master plan §1.1.
   - Introduction — 1.5 pages with the model-check-deliberation framing.
   - Background — `\todo{cite}` placeholders for entries from `papers/`.
   - Method — algorithm boxes scaffolded from the layer's API.
   - Theorems — `\begin{theorem}` blocks with statements verbatim from §10 of bible.
   - Empirics — table templates with `\todo{MLflow run missing}` placeholders.
   - Related work — `\todo{cite}` placeholders.
   - Limitations — explicit "what we don't claim" subsection.
   - References — `\bibliography{papers/refs}`.
4. **Generate `supplementary.tex`** with proof appendix, reproducibility appendix, extended ablations.
5. **Generate `Makefile`** with `make` (latexmk), `make clean`, `make watch`.
6. **Emit a report** listing files generated, theorem placeholders present, and the next-step recommendation.

## Invariants enforced
- Theorem statements come *verbatim* from §10 of the bible (no paraphrasing).
- Section headings come from §9 of the master plan (consistency across papers).
- Citations resolve to `papers/refs.bib` entries; missing ones are `\todo{cite}`.
- No invented results: every table cell starts as `\todo{MLflow run missing}`.

## Reject criteria
- `<paper_id>` not in {P1, P2, P3, P4, P5, F}.
- `papers/refs.bib` does not exist.
- `papers_drafts/<paper_id>_<slug>/` already exists (refuse to overwrite; user must delete first).
