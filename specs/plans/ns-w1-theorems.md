# Implementation Plan: feature/ns-w1-theorems (PR9 of W1)

## Overview

Final PR of W1. Documents and mechanises three theorems that justify the
verification spine for P1 (AAMAS 2027):

- **T1 — Soundness of LTL3 monitors** (cited from Bauer-Leucker-Schallhart 2011):
  if `monitor.step(e) = TOP` on a finite trace `w`, then every infinite extension
  of `w` satisfies `phi`; symmetrically for BOTTOM.
- **T2 — Compositionality** (original adaptation of Pnueli 1985 to dialogue
  setting): for monitors `M1, M2` of `phi1, phi2`, the verdict of the AND-composed
  monitor agrees with `min(verdict(M1), verdict(M2))` under Kleene order.
- **T3 — No-go for consensus-only aggregation** (original): a CTLK invariant
  exists which no purely consensus-counting aggregator satisfies; we exhibit a
  counterexample trace and demonstrate that the W0 last-propose heuristic
  violates it. The COUNTEREXAMPLE half is now MCMAS-mechanised
  (`tests/integration/test_mcmas_t3_counterexample.py`, see ADR 0004); the
  full ablation row vs. MajorityVote/BordaCount/CondorcetAggregation requires
  the L2 aggregator and remains W2/P1 work.

## Tasks

### Task 1 — `docs/theory.md`

Sections `## T1`, `## T2`, `## T3` each with:
- Statement (formal, English-then-symbolic)
- Proof sketch (3-5 sentences)
- References (Bauer-Leucker-Schallhart 2011, Pnueli 1985, etc.)
- Pointer to mechanised test

### Task 2 — `tests/symbolic/verify/test_theorems.py`

- T1-Soundness: parametrised over (formula, trace) pairs from a
  hand-crafted suite + a randomised-but-seeded suite. For each pair,
  if `monitor.step(...) = TOP`, then a manual oracle confirms; same
  for BOTTOM. We use ProgressionMonitor as the model since it covers
  the full LTL_f fragment.
- T2-Compositionality: for several formula pairs `(phi1, phi2)` and
  several traces, verify
  `verdict(monitor_AND(phi1, phi2)) == min(verdict(M1), verdict(M2))`
  under the Kleene order BOTTOM < UNKNOWN < TOP.
- T3-No-go-consensus-only: build a trace where 3 agents Vote for the
  same option but the option lacks evidence; confirm
  `ProvenanceCompleteness` rejects it (`Verdict.BOTTOM`) while a
  hypothetical "simple majority" aggregator would accept it. Document
  the gap as motivation for L2.

## Final checkpoint

- [ ] `docs/theory.md` exists with §T1, §T2, §T3
- [ ] `uv run pytest tests/symbolic/verify/test_theorems.py` passes
- [ ] `uv run mypy council/` exits 0
- [ ] `uv run ruff check` clean
- [ ] W1 acceptance checklist (master plan §7) — all items checked off

## Risks

| Risk | Mitigation |
|---|---|
| T1 mechanised test relies on a circular oracle | Use independent definition: oracle steps the formula on the FULL trace via a different code path (e.g., evaluate semantically given the entire event sequence at once) |
| T2 compositionality breaks under negation interactions | Restrict to AND-compositions; document that OR-compositions need adaptation |
| T3 counterexample is contrived | Reference master plan §11 (P1 ablation table) and mark this PR as motivating, not exhaustive |
