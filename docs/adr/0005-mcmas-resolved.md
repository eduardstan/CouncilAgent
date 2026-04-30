# ADR-0005: MCMAS Access Resolved — W1 Acceptance Verified, T3 Counterexample Mechanised

## Status

Accepted — supersedes [ADR-0004](0004-mcmas-access-deferred.md) (2026-04-29).

## Date

2026-04-30

## Context

[ADR-0004](0004-mcmas-access-deferred.md) recorded that MCMAS access was
blocked: the URLs we tried at the time (`mcmas.org.uk`, `vas.doc.ic.ac.uk`,
several `doc.ic.ac.uk/~alessio/...` paths) did not resolve, and the manual
at `https://sail.doc.ic.ac.uk/software/mcmas/manual.pdf` instructs users to
email `mcmas@imperial.ac.uk` for a pre-compiled binary. We deferred the
W1 end-to-end acceptance check and the MCMAS-mechanised half of T3 to
future development.

Today (2026-04-30) the maintainers' page is back online at
<https://sail.doc.ic.ac.uk/software/mcmas/> and exposes two working
download paths for **MCMAS 1.3.0** (Linux x86_64, 827 KB, single ELF
binary, `Last-Modified: 2018-07-10`):

> **Note on version numbers.** The download is **MCMAS binary 1.3.0**
> (released 2018; the `mcmas` banner prints "MCMAS v1.3.0"). The
> companion **user manual is v1.2.2** (the title page reads "MCMAS v1.2.2:
> User Manual"). Imperial refreshes the manual less frequently than the
> binary, so the two version strings disagree but document the same tool
> for our purposes — the manual's ISPL grammar (§3.2) and reserved
> keywords (§3.2.3) are unchanged across the 1.2.2 → 1.3.0 increment.
> The ISPL emitter targets the manual's documented grammar and is
> verified against the 1.3.0 binary's behaviour.


| Path | URL | Notes |
|---|---|---|
| Form-tracked | <https://www.doc.ic.ac.uk/download/?package=mcmas-linux64> | Records name / institution / email for the maintainers' usage tracking. Recommended for first install. |
| Direct (Referer-gated) | <https://sail.doc.ic.ac.uk/software/mcmas/mcmas-linux64-download.tgz> | Requires the `Referer: https://sail.doc.ic.ac.uk/software/mcmas/` header; suitable for scripted / CI install. |

I downloaded the binary, placed it at `~/.local/bin/mcmas`, verified
`mcmas` prints the v1.3.0 banner and usage on bare invocation, and ran
the existing W1 acceptance test (`tests/integration/test_mcmas_offline.py`)
under `RUN_INTEGRATION=1`. Real MCMAS rejected our initial ISPL output
with two parse / type errors; both were fixed via TDD on this branch
(commit `dca535e`):

1. **Single-letter agent names collide with CTL path quantifiers.** Our
   ISPL declared `Agent A`, `Agent B`, `Agent C`, `Agent D` for the W1
   reference trace. MCMAS's parser interprets `A` and `E` as the CTL
   universal / existential path quantifiers (per manual §3.2.3 reserved
   keywords). Fix: `_sanitise()` in `council/symbolic/verify/ispl.py`
   now prefixes every council-agent identifier with `agent_`.
2. **Never-true APs cannot use `-1` or `!=`.** Our emitter used
   `position=-1` for atomic propositions that are never true in a trace.
   MCMAS rejects this with "out of bound in Environment.position=-1"
   (the `position` variable is declared `0..N`). A subsequent attempt
   using `position!=0` was rejected with "unexpected NOT" (manual §3.2
   has no `!=` token; the lexer reads `!=` as `!` + `=`). Fix: use
   `position=0 and position=1` — two positive-`=` checks against
   distinct in-range constants, joined by `and`. This is a pure `=`
   contradiction, well-typed, and parses cleanly.

After both fixes, the W1 acceptance test passes:

```
/tmp/...ispl has been parsed successfully.
  Formula number 1: (EF is_vote), is TRUE in the model
  Formula number 2: (EF (is_challenge && (EF is_vote))), is TRUE in the model
execution time = 0.007
number of reachable states = 8
```

The T3 counterexample is also mechanised (commit `7703df7`). On a
3-agent unanimous-vote-without-evidence trace, MCMAS reports
`AG(is_vote → has_evidence) = FALSE` over 4 reachable states —
confirming, at the external-verifier level, what the W1
`ProvenanceCompleteness` monitor reports as `Verdict.BOTTOM`. See
`tests/integration/test_mcmas_t3_counterexample.py` and
[`docs/theory.md`](../theory.md) §T3.

## Decision

**MCMAS access is resolved for the project.** The W1 verification spine's
end-to-end acceptance criterion is now satisfied; T3's counterexample
half is mechanised at both the pytest level and the MCMAS level.

Concrete implications:

1. The `RUN_INTEGRATION=1`-gated tests (`test_mcmas_offline.py` +
   `test_mcmas_t3_counterexample.py`) ARE the canonical verification.
   Anyone with the MCMAS binary on `PATH` can reproduce.
2. ISPL emitter (`council/symbolic/verify/ispl.py`) is now grounded in
   the manual; future emitter changes should cite the relevant manual
   section (§3.2 ISPL syntax, §3.2.3 reserved keywords, §3.2.4 grammar)
   in their commit message.
3. Documentation updated: [`docs/installation.md`](../installation.md)
   replaces the "MCMAS — email-gated access" section with verified install
   instructions for both download paths. The email template at
   [`docs/installation.md#mcmas-website-down-fallback`](../installation.md#mcmas-website-down-fallback) is
   kept as a backup procedure for users who cannot reach the URL or who
   want a different platform binary.
4. ADR-0004 is **superseded** by this ADR; its status line is updated
   accordingly. The body of ADR-0004 is preserved as the historical
   record of the deferral.

## Alternatives Considered

### Build MCMAS from source

**Rejected.** The MCMAS source code is still not openly distributed — the
download page exposes binaries only and the user manual §1.2 directs
non-Linux x86_64 users to email the maintainers. This is unchanged from
ADR-0004. We do not need source-build support today because the linux64
binary is sufficient for the project's primary development platform.

### Use a third-party Docker image

**Rejected.** Provenance still unclear; same argument as ADR-0004 §B.

### Continue with the NuSMV substitute

**Kept as a documented fallback** for the CTL fragment, not the primary
path. The L2 strategic / epistemic operators (CTLK, ATL) are not
expressible in NuSMV, so MCMAS remains required for the full T3 ablation
and for W6's MCMAS-verified-learned-protocols subtask. NuSMV stays in
[`docs/installation.md`](../installation.md) for users who cannot
obtain the MCMAS binary.

## Consequences

### Positive

- The W1 acceptance criterion in
  [`COUNCILAGENT_NS_MASTER_PLAN.md §7 W1`](../../COUNCILAGENT_NS_MASTER_PLAN.md)
  is **fully satisfied** end-to-end (ISPL emitter unit-tested + MCMAS
  verifies the two named properties on the canonical trace).
- T3's counterexample half is **mechanised**: the W1
  `ProvenanceCompleteness` monitor's `Verdict.BOTTOM` on a 3-agent
  unanimous-vote-without-evidence trace is independently confirmed by
  MCMAS reporting `AG(is_vote → has_evidence) = FALSE`.
  See [`docs/theory.md`](../theory.md) §T3.
- Constitution §11 receipt-completeness gains an external verifier
  citation: the receipt's `monitor_verdicts` can now be cross-checked
  against MCMAS's CTL semantics on the same Trace.
- W6 (ILP/ASP, scheduled for M5) MCMAS-verified-learned-protocols
  subtask is **unblocked**.
- P1 (AAMAS 2027) artefact-evaluation reproducibility now has a working
  MCMAS path; reviewers running the gated test will see the same TRUE /
  FALSE verdicts.

### Neutral

- MCMAS 1.3.0 is from July 2018: stable but not actively developed.
  We should pin this version in the install docs (already done in
  [`docs/installation.md`](../installation.md)) and note any
  future MCMAS update in a follow-up ADR.
- The ISPL emitter is now coupled to MCMAS 1.3.0's exact dialect (no
  `!=`, single-letter identifiers reserved, in-range value checks).
  Future MCMAS releases may relax these constraints; the emitter is
  conservative and will continue to work, but the structural unit tests
  in `tests/symbolic/verify/test_ispl.py` codify the conservative form.

### Still pending (out of scope for this ADR)

- The full T3 ABLATION ROW vs. `MajorityVote` / `BordaCount` /
  `CondorcetAggregation` requires the L2 aggregator (W2) and so remains
  W2/P1 work. The counterexample half (here) is the prerequisite, now
  cleared.
- MCMAS source distribution: still gated by emailing
  `mcmas@imperial.ac.uk`. The email template at
  [`docs/installation.md#mcmas-website-down-fallback`](../installation.md#mcmas-website-down-fallback) is
  retained as a backup access procedure.
- CI integration: `RUN_INTEGRATION=1` is opt-in. We have not added a CI
  matrix job that downloads MCMAS automatically; that's a follow-up
  engineering task, not blocking.

## References

- [ADR-0004 (superseded)](0004-mcmas-access-deferred.md) — the deferral
  decision being superseded
- [`docs/installation.md`](../installation.md) §"MCMAS — verified install"
  — verified install instructions
- [`docs/installation.md#mcmas-website-down-fallback`](../installation.md#mcmas-website-down-fallback) —
  retained as a backup access procedure
- [`docs/theory.md`](../theory.md) §T3 — counterexample now
  mechanised on MCMAS
- [`tests/integration/test_mcmas_offline.py`](../../tests/integration/test_mcmas_offline.py)
  — W1 acceptance test
- [`tests/integration/test_mcmas_t3_counterexample.py`](../../tests/integration/test_mcmas_t3_counterexample.py)
  — new T3 counterexample test
- [`council/symbolic/verify/ispl.py`](../../council/symbolic/verify/ispl.py)
  — ISPL emitter (MCMAS-conformant after commit `dca535e`)
- MCMAS user manual v1.2.2: <https://sail.doc.ic.ac.uk/software/mcmas/manual.pdf>
  (reference for the ISPL syntax and reserved-keyword constraints)
- Lomuscio, Qu, Raimondi. *MCMAS: an open-source model checker for the
  verification of multi-agent systems.* STTT 2017.
