# ADR-0007: Self-attack detection deferred to W2/PR8 via `tools.py`

## Status

Accepted.

## Date

2026-04-30

## Context

Bible §6.3 (lines 639-640) of `COUNCIL_NS_PLAN.md` describes self-attack
detection inside `build_qbaf`:

```
- Self-attacks (an argument that contradicts its own evidence) are detected
  via a sub-call to the verifier (Z3 / clingo) when claim.domain ∈ {ARITH, FOL}.
```

This is a structural integrity check: a Propose whose stated `claim.surface`
contradicts its own `claim.evidence` — e.g., a claim "x = 5" backed by
evidence proving "x ≠ 5" — should produce a self-attack edge in the QBAF
(or, equivalently, mark the Propose's argument with reduced base_score).
Detecting "claim contradicts evidence" requires symbolic-logic reasoning
(Z3 for ARITH; clingo for FOL); pure-Python heuristic checks would be
both unsound and incomplete.

Architecture rules forbid `argue/ → verify/` imports. The path to
Z3/clingo from `argue/` therefore has to go through `council/tools.py`
(`ToolClient`), which already exists as a W0 stub for MCP / Z3 / clingo /
Lean. This is the only path that respects the layer boundaries.

The question is *when* to land self-attack detection.

Three options were evaluated.

## Decision

**Defer self-attack detection to W2/PR8 (`feature/ns-w2-asp-extensions`),
behind the `[argue-asp]` extra. PR2's `build_qbaf` returns no self-attacks;
the QBAF's `attacks` tuple contains only Challenge-derived edges.**

When PR8 lands, the flow is:

```
council/symbolic/argue/builders.py
  → council/tools.py::ToolClient.check_consistency(claim, evidence,
                                                   domain) → bool
  → MCP server (Z3 for ARITH, clingo for FOL)
```

The new approved exception added to `.claude/rules/architecture.md` is:

> #7. **`council/symbolic/argue/asp_backends.py → council/tools.py`** —
> for self-attack detection and ASP-backed extension semantics. The tool
> client is *injected* via the builder's `tool_client: ToolClient | None`
> kwarg, never hardcoded.

PR2's `build_qbaf` signature does NOT include a `tool_client` parameter
yet. PR8 adds it, with a `None` default that preserves PR2-PR7 behaviour.
This is forward-compatible: every PR2-PR7 callsite (and every test) keeps
working when PR8 ships.

## Alternatives Considered

### Option A — Land self-attack detection in PR2

Add `tool_client: ToolClient | None = None` to `build_qbaf` now. When
non-None, call `tool_client.check_consistency(...)` per Propose with
ARITH or FOL domain.

**Rejected.** PR2's deliverable is "deterministic build_qbaf" — every
acceptance test should be runnable in the no-extras path, with no MCP
server, no Z3 binary, no clingo binary. Adding the `tool_client` param
in PR2 mixes the determinism story with the optional-dep story; it
clutters the PR2 review surface; and the PR2 tests would have to either
(a) skip the self-attack path entirely, leaving it untested, or (b)
require Z3/clingo to be installed for the test suite. Neither is right.

PR8 is the natural home: its whole purpose is the optional `[argue-asp]`
extra, including the new `argue/asp_backends.py → tools.py` exception.
Self-attack detection is one of the deliverables there.

### Option B — Implement a pure-Python heuristic for self-attack

Skip the verifier and use a string-matching heuristic: e.g., flag claims
whose surface contains "not" or "≠" relative to their evidence atoms.

**Rejected.** Heuristic self-attack detection is both unsound (false
positives on "not [easily] computable") and incomplete (misses any
contradiction not expressed via lexical negation). P2 (AAAI 2027)
reviewers will check whether self-attack detection is *sound and
complete on the tested fragments*; a string heuristic fails both
criteria. The bible's "via a sub-call to the verifier" wording is
deliberate — it is the verification spine's job, not the builder's.

### Option C — Add `argue/ → verify/` to the approved-exceptions list

Allow `builders.py → council/symbolic/verify/...` and call SPOT/MCMAS
machinery directly.

**Rejected.** SPOT and MCMAS check LTL_f / CTLK temporal properties over
event traces — they are not the right tool for "claim contradicts
evidence" checks (which want Z3 for ARITH and clingo for FOL). The L1
verification spine and the L2-self-attack path are different concerns.
Adding `argue/ → verify/` would couple two layers that should remain
independent.

## Consequences

**Positive:**

- PR2 ships in the no-extras path — `uv pip install councilagent` is
  enough to run `build_qbaf`. No Z3, no clingo, no MCP server required.
- PR2 acceptance tests are fully deterministic and runnable in CI without
  optional dependencies.
- PR8 has a clean, well-scoped purpose (the `[argue-asp]` extra),
  including this self-attack feature plus ASP-backed extension semantics
  (preferred / stable / grounded).
- The `tool_client` parameter, when added in PR8, is forward-compatible
  with all PR2-PR7 callsites.

**Neutral:**

- The W2 spec's "Patch C" / "Patch D" / "Patch E" already note this
  deferral. No documentation churn.
- The bible's example pseudocode for `build_qbaf` hints at self-attack
  detection inline; PR2's docstring acknowledges this gap and points to
  ADR-0007.

**Negative:**

- Until PR8 ships, a Propose that contradicts its own evidence enters the
  QBAF unattacked. Gradual semantics will weight it normally. This is a
  known coverage gap, documented in `specs/w2-argumentation.md §"Risk
  register"` Risk 2 and in this ADR.
- Reviewers reading PR2-PR7 tests in isolation will not see self-attack
  coverage. The PR8 tests fill this gap.

## References

- `council/symbolic/argue/builders.py` — implementation site (W2/PR2);
  docstring notes the deferral
- `council/symbolic/argue/asp_backends.py` — future implementation site
  (W2/PR8)
- `council/tools.py` — `ToolClient` (W0 stub; PR8 expansion)
- `COUNCIL_NS_PLAN.md §6.3` — bible specification (the "via a sub-call
  to the verifier" line)
- `.claude/rules/architecture.md §"Approved exceptions"` — list to which
  PR8 will add the `argue/asp_backends.py → tools.py` exception
- `specs/w2-argumentation.md §"Risk register"` Risk 2 — originating
  question
