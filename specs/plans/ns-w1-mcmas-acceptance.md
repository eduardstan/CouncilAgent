# Implementation Plan: feature/ns-w1-mcmas-acceptance

## Overview

The MCMAS download URL went live again (`https://sail.doc.ic.ac.uk/software/mcmas/`).
This branch closes the **dangling W1 acceptance criterion** from `COUNCILAGENT_NS_MASTER_PLAN.md §7 W1`:

> ISPL emitter for MCMAS; offline check on a 4-agent / 4-round example;
> verifies `EventuallyDecide` and `RefutationReachable`.

It also addresses the dangling line in [`docs/theory.md`](../../docs/theory.md):91-92:

> The full ablation against `MajorityVote`, `BordaCount`, and
> `CondorcetAggregation` via small-instance MCMAS is deferred to W2/P1.

— but only the **existence-of-a-counterexample-via-MCMAS** half. The full
"vs. three aggregators" ablation row genuinely belongs to W2 (the L2
aggregator hasn't been built yet); we keep that scoped out.

Today (2026-04-30) all of: ISPL emitter (PR6), 24 structural unit tests, and
the gated integration test exist. We satisfy the W1 criterion by installing
the real MCMAS binary, running the integration test for real, and fixing any
ISPL output the real binary rejects (via TDD). For T3, we also add a small
MCMAS-backed test that mechanises the "consensus without evidence" CTLK
counterexample on the actual model checker.

We then supersede ADR 0003 (MCMAS deferred) with ADR 0004 (MCMAS resolved)
and update `docs/install_spot.md`.

## Architecture Decisions

- **Install path: user-local `~/.local/bin/mcmas`.** Same convention as SPOT
  (Path B). Avoids requiring sudo. Makes it easy for any user following the
  install docs to reproduce.
- **Download URL: bypass the form.** The Imperial download form is for usage
  tracking; the direct tgz URL works (verified). Documentation will mention
  both paths and recommend the form for citation/usage-tracking courtesy
  while noting the direct URL as a fallback for automated CI.
- **No silent fallback.** If MCMAS is on PATH the integration test runs; if
  not, it skips. We do not auto-download in the test harness — that would be
  network-dependent and slow. The download lives in `docs/install_spot.md`.
- **TDD for any ISPL fix.** If real MCMAS rejects our ISPL output, write a
  failing reproduction test in `tests/symbolic/verify/test_ispl.py` first
  (with the exact MCMAS error string), THEN fix the emitter, THEN verify.
  This prevents silent regressions when SPOT/MCMAS versions change later.
- **T3 mechanisation: scope to the counterexample, not the full ablation.**
  Adding a MCMAS-backed verification of the 3-agent unanimous-vote-without-
  evidence counterexample is in scope (it directly satisfies the part of T3
  written today). The full ablation against `MajorityVote`/`BordaCount`/
  `CondorcetAggregation` requires the L2 aggregator and stays deferred to
  W2/P1.

## Task List

### Phase 1: Install MCMAS locally (foundation)

#### Task 1: Download + extract MCMAS into `~/.local/bin/`
- **Description:** Use the verified direct URL with `Referer` to fetch the
  tarball. Inspect contents. Place the `mcmas` binary on `PATH` via
  `~/.local/bin/`.
- **Acceptance:**
  - [ ] `which mcmas` returns `~/.local/bin/mcmas`
  - [ ] `mcmas -version` (or equivalent) prints a banner with the MCMAS version
  - [ ] The binary is executable and runs without missing-library errors
- **Verify:** Run `mcmas` with no args; expect a usage message, not a crash.
- **Dependencies:** None.
- **Files:** none in repo (system-level install).
- **Scope:** XS

### Phase 2: Run the W1 acceptance test for real (the discovery slice)

#### Task 2: Run `RUN_INTEGRATION=1 pytest tests/integration/test_mcmas_offline.py`
- **Description:** Execute the existing gated test against the freshly
  installed MCMAS. This is the **first live signal** of whether our ISPL
  emitter produces something MCMAS accepts. Outcomes are:
    - **Outcome A (test passes):** rare-but-good. Move directly to Phase 4.
    - **Outcome B (test fails because MCMAS reports a parse error or
      rejects the formula):** capture the exact stderr, drop to Phase 3 to
      fix via TDD.
- **Acceptance:**
  - [ ] The test runs (does not skip)
  - [ ] We have either green or a captured error message
- **Verify:** observe the test output.
- **Dependencies:** Task 1.
- **Files:** none yet.
- **Scope:** XS

### Phase 3: Fix any ISPL bugs discovered (TDD — only if Outcome B)

#### Task 3: Reproduce the failure as a structural unit test
- **Description:** If MCMAS rejected our ISPL, the failure is in
  `council/symbolic/verify/ispl.py`. Per the project's TDD discipline, first
  write a unit test in `tests/symbolic/verify/test_ispl.py` that asserts the
  *correct* output shape MCMAS expects (likely a fix to a section header,
  keyword, or formula syntax). The test must FAIL on the current emitter.
- **Acceptance:**
  - [ ] New test in `test_ispl.py` reproduces the bug at the structural level
  - [ ] Test fails on the branch tip before the fix
- **Verify:** `uv run pytest tests/symbolic/verify/test_ispl.py::<new_test> -v` → 1 failure
- **Dependencies:** Task 2 (with Outcome B).
- **Files:** `tests/symbolic/verify/test_ispl.py`
- **Scope:** XS

#### Task 4: Fix `ispl.py` to satisfy the new test + the integration test
- **Description:** Minimal change to `council/symbolic/verify/ispl.py` to
  produce ISPL that real MCMAS accepts. Re-run both the structural test and
  the integration test.
- **Acceptance:**
  - [ ] All existing structural tests still pass
  - [ ] The new test from Task 3 passes
  - [ ] `RUN_INTEGRATION=1 pytest tests/integration/test_mcmas_offline.py` passes
- **Verify:** full mypy / ruff / pytest clean.
- **Dependencies:** Task 3.
- **Files:** `council/symbolic/verify/ispl.py`, possibly `_encode_*` helpers
- **Scope:** S–M (depends on what MCMAS rejects; if multiple section issues,
  break into one fix-per-issue commit)

#### Phase 3b (alt): If multiple distinct ISPL bugs surface
Repeat Tasks 3 and 4 for each bug (one failing test → one minimal fix).
Each pass leaves the suite green.

### Checkpoint: Phase 3
- [ ] `RUN_INTEGRATION=1 pytest tests/integration/test_mcmas_offline.py` passes
- [ ] mypy strict: 0 errors
- [ ] ruff: clean
- [ ] Full pytest: all green (no regressions)

### Phase 4: T3 partial mechanisation (the theory.md dangling line)

#### Task 5: Add a MCMAS-backed counterexample test for T3
- **Description:** Add a new gated integration test
  `tests/integration/test_mcmas_t3_counterexample.py` that:
    1. Constructs a 3-agent trace where all three emit `Vote("X")` with
       empty `evidence` (the canonical T3 counterexample described in
       `docs/theory.md` §T3).
    2. Generates ISPL via `trace_to_ispl` with the formula
       `G(is_vote -> has_evidence)` (= `ProvenanceCompleteness`).
    3. Runs MCMAS on the ISPL.
    4. Asserts MCMAS reports the formula as **FALSE** on this trace
       (= the W1 monitor's `Verdict.BOTTOM` is mechanically confirmed by
       the model checker).

  Gated by `RUN_INTEGRATION=1` AND `mcmas` on PATH, like the existing
  acceptance test.

  Update `docs/theory.md` §T3 to:
    - Cross-reference the new test in the **Mechanisation** section.
    - Replace "deferred to W2/P1" with "the counterexample is mechanised
      by `tests/integration/test_mcmas_t3_counterexample.py` (gated); the
      vs.-`MajorityVote`/`BordaCount`/`CondorcetAggregation` ablation row
      remains W2/P1 work because those aggregators are not yet implemented."
- **Acceptance:**
  - [ ] New gated test exists and PASSES under `RUN_INTEGRATION=1`
  - [ ] `docs/theory.md` §T3 updated; "deferred to W2/P1" replaced with
        the precise scoping above
- **Verify:** `RUN_INTEGRATION=1 pytest tests/integration/test_mcmas_t3_counterexample.py -v`
- **Dependencies:** Phase 3 checkpoint.
- **Files:** `tests/integration/test_mcmas_t3_counterexample.py` (new),
  `docs/theory.md` (T3 section).
- **Scope:** S

### Phase 5: Documentation + ADR (closes the loop)

#### Task 6: Update `docs/install_spot.md` MCMAS section
- **Description:** Replace the "DEFERRED — see ADR 0003" framing with
  verified install instructions (the curl + tar + chmod + PATH dance from
  Task 1, plus the form URL for users who want to be visible to the
  maintainers). Mention that the binary `Last-Modified` timestamp is 2018
  (so it's a stable/old build, not a freshly maintained one). Note the
  Referer-header requirement.
- **Acceptance:**
  - [ ] Section "MCMAS — email-gated access" replaced with "MCMAS — verified install"
  - [ ] Both the form URL and direct URL documented; troubleshooting (Referer
        header) included
  - [ ] References ADR 0004 (next)
- **Verify:** read-through; instructions copy-pasteable.
- **Dependencies:** Phase 3 checkpoint.
- **Files:** `docs/install_spot.md`
- **Scope:** S

#### Task 7: Write ADR 0004 (MCMAS resolved, supersedes 0003)
- **Description:** New ADR via `/documentation-and-adrs`. Status:
  "Accepted; supersedes ADR 0003". Decision: MCMAS is now installed and the
  W1 acceptance test passes. Consequences: T3's counterexample is now
  MCMAS-mechanised (Task 5); the W6 MCMAS-verified-protocols subtask is
  now unblocked; the full T3 ablation row remains W2/P1.
- **Acceptance:**
  - [ ] `specs/adrs/0004-mcmas-resolved.md` exists with the standard ADR
        sections
  - [ ] `specs/adrs/0003-mcmas-access-deferred.md` Status updated to
        "Superseded by ADR 0004 (2026-04-30)"
- **Verify:** files render as Markdown.
- **Dependencies:** Task 6.
- **Files:** `specs/adrs/0004-mcmas-resolved.md` (new),
  `specs/adrs/0003-mcmas-access-deferred.md` (status update)
- **Scope:** S

#### Task 8: Sweep "deferred" qualifiers from existing references
- **Description:** Find remaining "ADR 0003" / "MCMAS deferred" /
  "future development" language in docstrings, code comments, and the
  master plan footnotes, and update each to point at ADR 0004 with the
  new framing.
- **Acceptance:**
  - [ ] `tests/integration/test_mcmas_offline.py` docstring references ADR 0004
  - [ ] `docs/mcmas_request_email.md` updated to note "no longer needed
        for direct download; still helpful for academic-courtesy citation"
  - [ ] No remaining "deferred" language in `docs/`, `specs/`, or
        `council/symbolic/verify/`
- **Verify:** `grep -rn "0003-mcmas\|MCMAS.*deferred" docs council specs tests`
  returns only the ADR 0003 file itself (the historical record).
- **Dependencies:** Task 7.
- **Files:** `tests/integration/test_mcmas_offline.py`,
  `docs/mcmas_request_email.md`, possibly other docs
- **Scope:** XS

### Checkpoint: Phase 5
- [ ] Documentation updated end-to-end
- [ ] ADR 0003 superseded
- [ ] All references point to ADR 0004
- [ ] Branch ready to merge

### Phase 6: Final verification + merge

#### Task 9: mypy + ruff + full pytest + merge into council-ns
- **Description:** Final pass; merge with `--no-ff`; delete the feature branch.
- **Acceptance:**
  - [ ] mypy strict: 0 errors
  - [ ] ruff: clean
  - [ ] pytest: all green; **`RUN_INTEGRATION=1` tests now in the passing set**
        (no longer skipped on this machine) — both the W1 acceptance test
        and the new T3 counterexample test
  - [ ] `council-ns` history shows a clean `merge(w1/post)` commit
- **Verify:** `git log --oneline council-ns -3`
- **Dependencies:** All prior tasks.
- **Files:** none (merge commit only).
- **Scope:** XS

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Real MCMAS rejects our ISPL with multiple errors | Med | Iterate Phase 3 (one TDD test per error); each pass leaves the suite green |
| `mcmas-linux64-download.tgz` is a 2018 build with a syntax dialect we don't match | Low–Med | Read the included manual; sync our emitter to the documented dialect, not a guess |
| MCMAS binary fails to run (missing libstdc++ / glibc) | Low | Document the apt packages needed; fall back to source build if Imperial publishes one |
| Test passes on this machine but not in CI | Low | The test is gated by `RUN_INTEGRATION=1` AND `mcmas` on PATH; CI must opt in. Unrelated to merging on `council-ns`. |
| The form-required download path collides with the direct URL approach | Low | Document both; let users choose. The direct URL was openly linked from `sail.doc.ic.ac.uk/software/mcmas/`, so it's not a circumvention — it's the underlying artefact. |
| T3 counterexample test exposes a deeper modelling issue (e.g., MCMAS evaluates `G` over the entire transition system, not just the trace) | Med | If so, restrict the Kripke encoding so the trace is the only computation path (already done via deterministic `Environment` agent). Document any encoding nuance in the new test's docstring. |

## Open Questions

None at planning time. We expect to discover ISPL-emitter bugs in Phase 2;
those become Tasks 3+4 (or repeated). If real MCMAS reveals a deeper modelling
issue (e.g., the bounded-trace Kripke encoding doesn't match what MCMAS expects
for CTL evaluation on a finite-trace acceptance), that becomes a new ADR.

## Notes for the implementer

- Keep one logical change per commit: the install steps (Task 1) are
  not committed at all (system-level); each ISPL fix is one commit; the docs
  update is one commit; the ADRs are one commit; the merge is one commit.
- Do not commit the downloaded MCMAS tarball or binary into the repo — they
  are not redistributable under the project's licence.
- The ADR 0003 status update is a Markdown edit, not a deletion. Keep the
  historical record intact.
- T3's two-part scope (counterexample mechanised here; full ablation in W2)
  must be reflected exactly in `docs/theory.md` to avoid an over-claim.
