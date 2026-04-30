# ADR-0004: MCMAS Binary Access — Deferred to Future Development

## Status

**Superseded by [ADR-0005](0005-mcmas-resolved.md) (2026-04-30).**

The access situation that motivated this ADR was resolved a day later: the
maintainers' page at <https://sail.doc.ic.ac.uk/software/mcmas/> came back
online and exposes a working download for MCMAS 1.3.0 (Linux x86_64).
ADR-0005 records the verified install procedure, the two ISPL-emitter bugs
that real MCMAS surfaced (and their fixes), and the W1 / T3 verification
results.

The body of this ADR is preserved as the historical record of the deferral
decision and the diagnostic dead-ends we tried (URL probing, email-request
template, NuSMV substitute). None of that work was wasted —
`docs/installation.md#mcmas-website-down-fallback` is retained as a backup procedure for users
who cannot reach the URL or who need a non-Linux-x86_64 binary.

*Original status (2026-04-29): Accepted (interim) — to be revisited when
MCMAS access is obtained.*

## Date

2026-04-29

## Context

W1's verification spine includes an "offline check on a 4-agent / 4-round
example; verifies `EventuallyDecide` and `RefutationReachable`" via MCMAS, the
multi-agent CTLK/ATL model checker by Alessio Lomuscio (Imperial College London).
This requirement is stated in [`COUNCILAGENT_NS_MASTER_PLAN.md §7 W1`](../../COUNCILAGENT_NS_MASTER_PLAN.md):

> ISPL emitter for MCMAS; offline check on a 4-agent / 4-round example;
> verifies `EventuallyDecide` and `RefutationReachable`.

W1/PR6 implemented the ISPL emitter ([`council/symbolic/verify/ispl.py`](../../council/symbolic/verify/ispl.py))
and 32 structural unit tests confirm the output is well-formed. The only piece
missing is the MCMAS binary itself, which is required by
[`tests/integration/test_mcmas_offline.py`](../../tests/integration/test_mcmas_offline.py)
to actually run the verification and confirm the formulae hold on the
generated ISPL.

### MCMAS access procedure (clarified 2026-04-29)

After investigation, the canonical MCMAS distribution channel is **email
request to the maintainers**, not a direct download. The project's user
manual at <https://sail.doc.ic.ac.uk/software/mcmas/manual.pdf> §1 states:

> "We might be able to provide a pre-compiled binary version for your system,
> please contact us at mcmas@imperial.ac.uk."

The source code is **not** openly distributed. This is a deliberate choice
by the maintainers (Alessio Lomuscio's group, Imperial College London) and
constrains accessibility for any user of this project.

#### Earlier failed download attempts (recorded for the public record)

| URL | Outcome |
|-----|---------|
| `https://mcmas.org.uk/` | No response (referenced in earlier doc drafts) |
| `https://www.doc.ic.ac.uk/~alessio/mcmas.html` | HTTP 404 |
| `https://www.doc.ic.ac.uk/~alessio/MCMAS/` | HTTP 404 |
| `https://vas.doc.ic.ac.uk/software/mcmas/` | Timed out |
| `https://sail.doc.ic.ac.uk/software/mcmas/` | Page exists but not direct download |
| `https://sail.doc.ic.ac.uk/software/mcmas/manual.pdf` | **Resolves** — contains the email-request instructions |

GitHub / SourceForge contain only:
- `mcmassc` on SourceForge (a different slot-checking variant)
- `MCMAS-G` (a quantitative-trust derivative)
- `mattvonrocketstein/docker-mcmas` (unmaintained, version unclear)

None of these are the canonical model checker.

## Decision

**Defer MCMAS-dependent work to future development.** Specifically:

1. The ISPL emitter (`council/symbolic/verify/ispl.py`) is considered
   structurally correct, validated by 32 unit tests, but **not yet end-to-end
   verified against MCMAS itself**. We are confident in our generation; we
   cannot today certify that MCMAS accepts and successfully checks the output.

2. `tests/integration/test_mcmas_offline.py` remains in the codebase but is
   gated by `RUN_INTEGRATION=1` AND `mcmas` being on PATH. With current
   conditions, it skips. The test is **correct**; the missing piece is the
   binary, not the test.

3. The W1 acceptance criterion in [`COUNCILAGENT_NS_MASTER_PLAN.md §7`](../../COUNCILAGENT_NS_MASTER_PLAN.md)
   is **partially satisfied**: the ISPL emitter exists and is unit-tested, but
   the MCMAS verification of `EventuallyDecide` + `RefutationReachable` on a
   4-agent / 4-round example is pending. We will not relax our description of
   what is verified versus what is generated.

4. T3 in [`docs/theory.md`](../theory.md) cites "small-instance MCMAS"
   verification of un-satisfiability for `MajorityVote`, `BordaCount`,
   `CondorcetAggregation`. The MCMAS-dependent part of T3 is therefore
   **deferred to W2 / P1**, alongside the L2 aggregator implementation.

5. W6 (ILP/ASP, scheduled for M5) requires "MCMAS-verified learned protocols"
   per [`COUNCILAGENT_NS_MASTER_PLAN.md §7 W6`](../../COUNCILAGENT_NS_MASTER_PLAN.md).
   That workstream will need to address the MCMAS access issue when it begins.
   Mitigation note added to the W6 plan when it is created.

## Alternatives Considered

### A. Build MCMAS from source

**Rejected.** No public source repository found at the URLs tested. MCMAS
historically was distributed as a closed-source binary. Even if the source
becomes available, build dependencies (CUDD library, GMP) and licensing terms
are not currently confirmable from this session.

### B. Substitute NuSMV for the CTL fragment

**Accepted as interim alternative.** The project already includes
[`trace_to_smv()`](../../council/symbolic/verify/smv.py) which emits NuSMV-format
modules. NuSMV supports CTL (sufficient for `EventuallyDecide = EF(is_vote)` and
`RefutationReachable = EF(is_challenge ∧ EF(is_vote))`) but **not** CTLK/ATL
(needed for T3's epistemic invariants and for W6's full strategic-logic checks).

NuSMV is currently distributed at <https://nusmv.fbk.eu> — the project is alive
and version 2.7.1 is the latest release as of 2026-04-29 (per FBK's Tools
group). Source and pre-compiled binaries are available after filling a short
academic-use form. Licence: free for academic / educational research; commercial
use requires a separate agreement.

Caveat: NuSMV is not in the Ubuntu 24.04 default apt archive, so the interim
path also requires a manual download from <https://nusmv.fbk.eu>. This is
documented in [`docs/installation.md`](../installation.md) under
"Optional: NuSMV interim CTL path".

The NuSMV interim path is suitable for **all of W1's acceptance work** because
the two named properties (`EventuallyDecide`, `RefutationReachable`) live in
plain CTL. The MCMAS gap affects only future epistemic/strategic extensions.

### C. Use a Docker image (e.g. `mattvonrocketstein/docker-mcmas`)

**Rejected.** Provenance unclear: the wrapper is unmaintained, the bundled
MCMAS version is not stated, and the licensing terms of the embedded binary
are not documented. Using an unverified third-party container as a verification
oracle would undermine the soundness claims that depend on the verifier.

## Consequences

### Positive

- The W1 codebase remains complete and shippable. All structural correctness
  is unit-tested and can be verified via `uv run pytest tests/symbolic/`.
- NuSMV can substitute for MCMAS on the W1 acceptance check (CTL fragment).
- The integration test, the spec, and this ADR clearly delimit what is
  verified versus what is pending.

### Negative

- T3's "small-instance MCMAS" verification claim is downgraded: the proof
  sketch in [`docs/theory.md`](../theory.md) §T3 is currently a counterexample
  *demonstration*, not a fully mechanised model-checking result. P1 (AAMAS 2027)
  must either obtain MCMAS before submission or recast T3 as NuSMV-checked-CTL
  + manual-CTLK argumentation.
- W6 work cannot start its "MCMAS-verify induced rules" subtask until access
  is resolved. The rest of W6 (Popper / ILASP4 mining) is unaffected.

### Future Development (when MCMAS is obtained)

1. Send the email request at [`docs/installation.md#mcmas-website-down-fallback`](../installation.md#mcmas-website-down-fallback)
   to <mcmas@imperial.ac.uk> from an institutional address.
2. Once a binary arrives:
   - Place `mcmas` on PATH; verify with `mcmas -version`.
   - Add a verified install section to [`docs/installation.md`](../installation.md)
     replacing the "MCMAS — DEFERRED" block.
3. Re-run `RUN_INTEGRATION=1 uv run pytest tests/integration/test_mcmas_offline.py`
   (already gated; should pass automatically once `mcmas` is on PATH).
4. Update T3 in `docs/theory.md` with the actual mechanised CTLK verification
   results.
5. Open a follow-up branch `feature/ns-w1-mcmas-acceptance` to bundle the
   binary install + test re-enable + T3 update; supersede this ADR.

### Accessibility implication for downstream users

The email-request gate means **any user of CouncilAgent‑NS who needs the
W6 (ILP/ASP) MCMAS-verified-protocols pipeline must independently obtain
MCMAS by emailing the Imperial College team**. The CouncilAgent‑NS repo
**cannot bundle MCMAS** under its own license, and we cannot guarantee that
every user will be able to obtain it. This affects reproducibility of
publications P1 (AAMAS 2027) and P5 (KR 2027; the original KR 2026 target
is past, see master plan §1.2 publication-track realignment 2026-04-30).
Mitigation:

- Document the gate prominently in `README.md` (when one is added).
- When P1 / P5 reach submission, include in the artefact-evaluation README
  a clear note that MCMAS is required for the corresponding ablation rows
  and provide instructions for obtaining it.
- Where feasible, include NuSMV-substituted CTL-only ablations as a public
  fallback, marked clearly as "without epistemic / strategic operators."

## References

- [`COUNCILAGENT_NS_MASTER_PLAN.md §7 W1`](../../COUNCILAGENT_NS_MASTER_PLAN.md) — original acceptance criterion
- [`docs/theory.md §T3`](../theory.md) — depends on MCMAS for full mechanisation
- [`council/symbolic/verify/ispl.py`](../../council/symbolic/verify/ispl.py),
  [`council/symbolic/verify/smv.py`](../../council/symbolic/verify/smv.py) — emitters
- [`tests/integration/test_mcmas_offline.py`](../../tests/integration/test_mcmas_offline.py) — gated test
- Lomuscio, Qu, Raimondi. *MCMAS: an open-source model checker for the verification of multi-agent systems.* STTT 2017. (cited in `docs/theory.md` and the W1 spec)
