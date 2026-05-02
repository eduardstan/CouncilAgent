# Spec: T5 + T6 — closing P2's remaining theorem revisions

**Branch:** `council-ns` → `feature/theorem-t5-t6-revision`
**Status:** READY TO START — predecessor T7 ATLK revision merged at `128df5e`.
**Paper coupling:** P2 *Strategic Gradual Argumentation* (AAAI 2027 ≈ Aug 1 2026 ≈ 12 weeks). After this work P2's full theorem block (T4 ready, T5+T6+T7 closed) is locked; remaining P2 work is empirics only (W7).
**Predecessor:** v0.2.2 + T7 revision shipped on `council-ns`. The current T5/T6 audit verdicts (`~/.claude/projects/-home-eduard-Dropbox-Projects-CouncilAgent/memory/project_theorem_audit_v2.md`) are:

  - **T5:** NEEDS-REVISION (Phase 0 done; deeper revision pending — ~1-2 days)
  - **T6:** READY (with citation nit — ~0.5 day; **the user added the Caminada-Amgoud 2007 AIJ paper to `papers/3` on 2026-05-02, closing the bibliographic-attestation half of the nit; only the citation-text correction + docstring sharpening remain**)

---

## Objective

Close T5 and T6 cleanly so P2's theorem section is finalised. The work is split across two theorems but driven by the same principle: **mathematically grounded, no workarounds**. Specifically, the theorem-audit-v2 recommendation for T5 ("refined-bound corollary using Baroni-Rago-Toni 2019 §4.3 on manipulability quantification") is **factually wrong**: the paper has no §4.3 and contains no manipulability-bound result. The current `docs/theory.md` line 484 also carries this broken citation. This spec corrects both.

A second factual finding shapes T6: the user added `papers/3 --- argumentation/Caminada and Amgoud 2007 "On the evaluation of argumentation formalisms" (Artificial Intelligence).pdf` (the AIJ paper) on 2026-05-02. The current docs/theory.md citation reads "Caminada, Amgoud. *On the issue of contamination in abstract argumentation frameworks*. ECSQARU 2007" — a different Caminada-Amgoud 2007 paper. The honest fix: update the citation to the AIJ paper now on disk, which IS the canonical rationality-postulates source.

Why this matters. P2 is the AAAI 2027 paper. T5 (manipulability bound) is the adversarial-robustness theorem reviewers will scrutinise; T6 (Caminada-Amgoud postulate matrix) is the characterisation theorem. Both must be unimpeachable.

**Users:**
- P2 paper writers (the spec, the proofs, the appendix table)
- AAAI argumentation reviewers (will fact-check citations against the cited PDFs)
- The W2 callers of `manipulability.py::flip_cost` and `flip_cost_upper_bound` (interface preserved)

**Success:**
- Every success criterion in §"Success Criteria" below is met
- `theorem-checker` re-audit reduces T5 from `NEEDS-REVISION` to `READY` and confirms T6 stays `READY`
- mypy strict 0 errors; ruff clean
- Pre-existing T5 + T6 tests in `tests/regressions/` all still pass

---

## The math (precise statements after revision)

### T5 (revised, narrowed to DF-QuAD)

> **T5 (Manipulability Bound for DF-QuAD).** Let `Q` be a QBAF with `proposals(Q)` denoting the set of non-withdrawn arguments (per ADR-0010 Q2), `n = |proposals(Q)|`, and `sem = DFQuADSemantics()` under which a unique winner is well-defined. Define the **flip cost** `flip_cost(Q, sem)` as the minimum number of binary attack-edge perturbations — each toggling an ordered pair `(s, t)` of distinct non-withdrawn arguments between weight 0 (absent) and weight 1 (full attack) — required to change the winner. Then:
>
> ```
> flip_cost(Q, sem)  ≤  max(0, n − 1)
> ```
>
> with the convention that `flip_cost = 0` when `n = 0` (vacuous) and `flip_cost = -1` (sentinel for "unflippable") when `n = 1` (no swap target).

**What changes from the current version.** The statement narrows from "any gradual semantics under which a unique winner is well-defined" to **DF-QuAD specifically**. The proof was already DF-QuAD-specific (uses the saturating ℱ-aggregation `v_a(w) = 1 - ∏_{a ≠ w} (1 - strength(a))` explicitly); the previous statement over-generalised. Either narrow or generalise — narrowing is honest and faster; generalising would require new work for QE/Ebs.

### T6 (no statement change, two-citation cleanup)

The statement and matrix are unchanged. The only changes are to the **References** section:

- **Caminada-Amgoud 2007** is corrected from the ECSQARU contamination paper to the AIJ paper now on disk: *"On the evaluation of argumentation formalisms"*, Artificial Intelligence 171(5-6), 286-310. This is the canonical rationality-postulates source for *extension* semantics.
- **Amgoud-Ben-Naim 2018 (IJAR)** remains the primary bibliographic citation for what the matrix actually tests: the *gradual-semantics analogues* of the rationality postulates (Definitions 8-14 + Table 1). This is what we satisfy/violate; Caminada-Amgoud 2007 is the parent reference for the postulate idea but not for our specific gradual-semantics formulations.

Both citations are now load-bearing and both PDFs are on disk.

---

## The verified factual finding (BRT 2019 §4.3 is fictional)

During spec drafting (2026-05-02 session) I extracted the section structure from `papers/3 --- argumentation/Baroni et al. 2019 ...IJAR.pdf` via `pdftotext` and grepped:

- `^4\.|^4\.[0-9]` → `4.` (intro to §4 "(Strict) balance/monotonicity principles"), `4.1.` ("(Strict) balance"), `4.2.` ("(Strict) monotonicity"). **No §4.3.**
- `manipulab` → 1 hit ("adversarial settings" reference, not a manipulability bound)

The audit-v2's recommendation to "add refined-bound corollary using BRT 2019 §4.3" therefore points to nothing that exists. Acting on it would produce a fabricated citation. The honest revision:

1. Remove the broken `§4.3 on manipulability quantification` parenthetical from the existing T5 BRT 2019 citation (line 484 of theory.md).
2. If a BRT 2019 reference remains in T5, point at §4.2 (monotonicity principles), which IS the relevant content — strict monotonicity bounds how strength changes with attack additions, which is *related* to manipulability but does not directly give a refined manipulability bound.
3. Flag the refined-bound corollary as **honest future work** in T5's "Tightness and refinements" paragraph, with a placeholder for a properly-derived in-degree-parameterised bound.

This is the senior-engineer move. The audit was not infallible; the BRT 2019 §4.3 reference is a verifiable error, not an open question.

---

## Tech Stack

- Python 3.11+, `mypy --strict` on `council/`, `ruff`
- `pytest` + `pytest-asyncio` (mode = `auto`)
- **No MCMAS subprocess required** — T5 and T6 are pure-Python algebraic / property-based work.
- No new optional dependencies.

---

## Commands

```bash
# Targeted unit tests
uv run pytest tests/regressions/test_t5_manipulability.py tests/regressions/test_t6_postulates.py -v

# Full unit suite (regression check)
uv run pytest tests/

# Type-check + lint
uv run mypy council/
uv run ruff check council/ tests/

# Theorem-checker re-audit (after revision committed)
# (invoked via the theorem-checker subagent with focus on T5 + T6)
```

---

## Project Structure

Files modified by this revision (no new files; this is a theorem-revision PR):

```
docs/
└── theory.md                                    MODIFIED — §T5 narrowed; §T5+§T6 references cleaned

council/symbolic/argue/
└── manipulability.py                            (likely UNCHANGED — implementation already correct)

tests/regressions/
├── test_t5_manipulability.py                    MODIFIED — extend property-based test from N=4 to N∈[2,5]
└── test_t6_postulates.py                        MODIFIED — sharpen docstrings on saturation-boundary tests
```

No new ADRs are needed. The substantive decisions (narrowing T5 to DF-QuAD; not fabricating a refined bound; using both Amgoud-Ben-Naim 2018 and Caminada-Amgoud 2007 AIJ as primary T6 references) are documented inline in the spec and in the theorem text itself, which is the appropriate venue.

---

## Code Style

Follow `.claude/rules/code-style.md`. Test docstrings use the project's existing pattern (mirror `tests/regressions/test_t7_coupled.py` for shape — short prose explaining what each test pins).

For T5's property-based test, parameterise by `N` using `pytest.mark.parametrize`:

```python
@pytest.mark.parametrize("n_args", [2, 3, 4, 5])
def test_flip_cost_bounded_by_upper_bound_property(n_args: int) -> None:
    rng = random.Random(0)
    for _ in range(20):
        qbaf = _random_qbaf(n_args, rng)
        ...
```

This gives `4 × 20 = 80` random instances across the parameterised range, vs. the current `1 × 20 = 20` at `N=4`.

---

## Testing Strategy

### Pre-existing tests (must continue to pass)

- `tests/regressions/test_t5_manipulability.py` — `TestFlipCostUpperBound`, `TestFlipCostExact`, `TestFlipCostBoundedByUpperBound`. **All pass.**
- `tests/regressions/test_t6_postulates.py` — 16 test classes (9 satisfied + 6 violated + 1 documented), plus `TestPostulateMatrix` cardinality check. **All pass.**

### Modified tests

- `TestFlipCostBoundedByUpperBound` extends from a fixed-`N=4` random sweep to a `pytest.mark.parametrize`'d sweep over `N ∈ {2, 3, 4, 5}`. The seed remains `0` for reproducibility.
- `TestStrictReinforcementViolated` and `TestStrictFranklinViolated` get sharpened docstrings explaining (a) the canonical Amgoud-Ben-Naim 2018 antecedent, (b) why DF-QuAD's saturating ℱ-aggregation violates it at the `base = 1.0` boundary, and (c) what the test fixture's specific saturation construction captures. The test bodies do NOT change.

### Out-of-scope tests

- New tests for a refined-bound corollary — flagged as honest future work, not shipped here.
- Tests for QE/Ebs manipulability — narrowing T5 to DF-QuAD makes these out of scope.

---

## Boundaries

### Always do

- Verify every paper-section citation against the actual PDF before committing it. The BRT 2019 §4.3 finding shows why this matters.
- Preserve the public API of `manipulability.py` (`flip_cost`, `flip_cost_upper_bound` signatures). The revision is theorem-side, not code-side.
- Keep T6's matrix unchanged. The 9-satisfied / 6-violated / 1-N/A breakdown is locked.
- Cite Amgoud-Ben-Naim 2018 AND Caminada-Amgoud 2007 (AIJ) by file path in T6's References section.

### Ask first

- Any change to the matrix in T6 (cardinalities, satisfied/violated/N-A column).
- Any change to `manipulability.py` (the implementation is already correct per Phase 0).
- Adding a new theorem (T5.refined as a corollary) — the spec defers this to future work.

### Never do

- Cite a paper section that has not been verified to exist in the PDF.
- Fabricate a refined bound and attribute it to a paper that doesn't contain it.
- Generalise T5's statement to `sem ∈ {QE, Ebs}` without first generalising the proof.
- Remove pre-existing T5 or T6 tests; this is a refinement, not a rewrite.

---

## Success Criteria (precise, testable)

1. **`docs/theory.md` §T5 statement** narrows to DF-QuAD specifically. The opening line reads "Let `Q` be a QBAF ... and `sem = DFQuADSemantics()`" (or equivalent) instead of "any gradual semantics under which a unique winner is well-defined".
2. **The broken `§4.3 on manipulability quantification` citation is removed.** If a BRT 2019 reference remains, it points to §4.2 (monotonicity), which is verified to exist in the PDF.
3. **`docs/theory.md` §T5 "Tightness and refinements"** flags a refined in-degree-parameterised bound as honest future work, with no fabricated attribution.
4. **`docs/theory.md` §T6 References** lists both Amgoud-Ben-Naim 2018 AND Caminada-Amgoud 2007 (AIJ) with their correct titles and venues, both pointing at file paths in `papers/3 --- argumentation/`.
5. **`tests/regressions/test_t5_manipulability.py::TestFlipCostBoundedByUpperBound`** is parameterised over `N ∈ {2, 3, 4, 5}`. Total: ~80 random instances assert `flip_cost ≤ upper_bound`.
6. **`tests/regressions/test_t6_postulates.py::TestStrictReinforcementViolated`** and **`TestStrictFranklinViolated`** have sharpened docstrings describing the saturation-boundary instantiation. Test bodies unchanged.
7. **mypy --strict 0 errors** on all modified `council/` files (likely zero changes needed).
8. **ruff** clean across `council/` and `tests/`.
9. **theorem-checker re-audit** on T5: verdict reduces from `NEEDS-REVISION` to `READY` (or `NEEDS-MINOR-REVISION` with no architectural concerns).
10. **theorem-checker re-audit** on T6: verdict stays `READY`; the Caminada-Amgoud 2007 PDF-not-on-disk concern is closed (PDF added by the user; citation corrected to the AIJ paper).

---

## Open Questions

**None.** The BRT 2019 §4.3 finding is a verified fact, not an open question; the audit's recommendation was incorrect and is corrected here. The Caminada-Amgoud 2007 citation venue is now corrected to the AIJ paper, which is on disk.

---

## Cross-chat handoff context

A fresh session resuming this work should know:

1. **Decisions are locked.** Narrow T5 to DF-QuAD; do not fabricate a refined-bound corollary; correct the Caminada-Amgoud 2007 citation venue from ECSQARU (not on disk) to AIJ (on disk).
2. **Branch.** `feature/theorem-t5-t6-revision`, branched from `council-ns` at `128df5e` (post-T7).
3. **Memory.** `~/.claude/projects/-home-eduard-Dropbox-Projects-CouncilAgent/memory/project_theorem_audit_v2.md` — but the BRT 2019 §4.3 entry is a verified bug in the audit; this spec corrects it.
4. **Reference docs.**
   - `docs/theory.md` §T5 (lines 427-504) and §T6 (lines 506-580)
   - `council/symbolic/argue/manipulability.py` — the implementation
   - `tests/regressions/test_t5_manipulability.py` — pre-existing tests
   - `tests/regressions/test_t6_postulates.py` — pre-existing tests
   - `papers/3 --- argumentation/Amgoud and Ben-Naim 2018 ...IJAR.pdf` — primary T6 reference (gradual-semantics analogues)
   - `papers/3 --- argumentation/Caminada and Amgoud 2007 "On the evaluation of argumentation formalisms" (Artificial Intelligence).pdf` — added 2026-05-02; foundational extension-semantics rationality postulates
   - `papers/3 --- argumentation/Baroni et al. 2019 ...IJAR.pdf` — relevant for T5's monotonicity-related framing only (§4.2, NOT §4.3)
   - `COUNCILAGENT_NS_MASTER_PLAN.md` §9 P2 — the AAAI 2027 paper structure
5. **Estimated effort.** 1.5-2 person-days (T5: ~1 day with the test parameterisation + theorem narrowing + citation correction; T6: ~0.5 day for citation venue correction + docstring sharpening).

---

## References

- `~/.claude/projects/-home-eduard-Dropbox-Projects-CouncilAgent/memory/project_theorem_audit_v2.md` — the audit driving this revision (with the corrected BRT 2019 §4.3 finding noted in this spec).
- `docs/theory.md` §T5 (lines 427-504), §T6 (lines 506-580).
- `papers/3 --- argumentation/Amgoud and Ben-Naim 2018 "Evaluation of arguments in weighted bipolar graphs" (IJAR).pdf`.
- `papers/3 --- argumentation/Caminada and Amgoud 2007 "On the evaluation of argumentation formalisms" (Artificial Intelligence).pdf` (added 2026-05-02 by the user).
- `papers/3 --- argumentation/Baroni et al. 2019 "From fine-grained properties to broad principles for gradual argumentation: A principled spectrum" (IJAR).pdf`.
- `COUNCILAGENT_NS_MASTER_PLAN.md` §9 P2.
- `specs/t7-atlk-revision.md` — sister revision spec; same workflow conventions.
- ADRs 0008-0021 — sibling rationale convention.
