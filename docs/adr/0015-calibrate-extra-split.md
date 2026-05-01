# ADR-0015: `[calibrate]` extra owns numpy + scipy + scikit-learn; `[benchmark]` includes it transitively

## Status

Accepted.

## Date

2026-05-01

## Context

W3 (L3 Calibrated Disagreement) ships four concrete `Calibrator` subclasses:
`JSDCalibrator`, `MUSECalibrator`, `PrivilegedKnowledgeCalibrator`,
`IsotonicCalibrator` (see `COUNCILAGENT_NS_MASTER_PLAN.md §7 W3`). All four
require the standard scientific-Python stack:

  - `numpy` — array math, distribution support handling
  - `scipy` — `scipy.spatial.distance.jensenshannon`, `scipy.stats` for MUSE
  - `scikit-learn` — `IsotonicRegression` for PR4

Until 2026-05-01 these three packages lived in the `[benchmark]` extra
(lines 33-42 of `pyproject.toml`), alongside `datasets`, `mlflow`,
`statsmodels`, and `hydra-core`. The semantic justification for `[benchmark]`
is "Bootstrap, Wilcoxon, AIPW, Bradley-Terry, mixed-effects" — i.e.,
**evaluation-side** statistics that live outside `council/` (under
`evaluation/` and `experiments/`).

The architecture rules (`.claude/rules/architecture.md` §"Forbidden imports")
prohibit `council/calibrate/` from depending on `evaluation/` or
`experiments/`, and by extension on extras whose semantics describe those
layers. If `council/calibrate/jsd.py` had to import `numpy` "via
`[benchmark]`", a future reader scanning the dependency graph would see L3
code conditionally available behind an extra named after `evaluation/`'s
needs — that is exactly the §3 layering blur Constitution principles aim to
prevent.

The W3 spec ([`specs/w3-calibration.md`](../../specs/w3-calibration.md)
§"Resolved decisions" Q1) commits to splitting the extra. This ADR
documents the rationale and the chosen implementation shape.

## Decision

**Define a new `[calibrate]` extra in `pyproject.toml` that owns
`numpy>=1.26`, `scipy>=1.13`, and `scikit-learn>=1.5`. Refactor `[benchmark]`
to depend on `"councilagent[calibrate]"` rather than re-listing the
numerics. Existing `uv sync --extra benchmark` users keep the same
transitive dependency closure; new `uv sync --extra calibrate` users get
exactly the L3 numeric stack and nothing else.**

The W3 PRs (`feature/ns-w3-jsd`, `feature/ns-w3-muse`,
`feature/ns-w3-privileged`, `feature/ns-w3-isotonic`,
`feature/ns-w3-terminations`) all declare `[calibrate]` as their dependency
target. CI matrices that exercise L3-only paths install with
`--extra calibrate --extra dev`, never `--extra benchmark`.

## Alternatives Considered

### Option A — Keep numerics in `[benchmark]` only; have W3 calibrators import from there

Leave `pyproject.toml` unchanged. Document in `council/calibrate/`'s
docstrings that the layer requires `[benchmark]` at install time.

**Rejected.** Two reasons:

1. **Layer-semantic violation.** The architecture rules forbid `council/`
   from depending on `evaluation/`-flavoured extras. The intent rule
   (§"Forbidden imports") is broader than the literal import-edge check —
   "L3 must be installable as L3, without pulling in `evaluation/`'s
   numeric machinery". A user installing `councilagent[calibrate]` (an
   extra that does not exist under Option A) should still get a working L3.
2. **Citation/discovery.** Future agents and humans reading
   `council/calibrate/__init__.py` will look at the extras list to
   determine the dependency. Pointing them to `[benchmark]` mis-describes
   what the layer is and what it needs.

### Option B — Duplicate the numeric pins in both `[calibrate]` and `[benchmark]`

Both extras list `numpy>=1.26`, `scipy>=1.13`, `scikit-learn>=1.5` directly.
No transitive include.

**Rejected for drift risk.** When the next dependency bump arrives (e.g.,
`scipy>=1.14` for some MUSE-required function), one extra will be edited
and the other forgotten. Two-source-of-truth pinning has caused real
incidents in `legacy_council/` (D17 in the deep-review). The PEP-508
`"councilagent[calibrate]"` re-export in `[benchmark]` is the canonical
fix: one place owns the pin, dependants get it transitively.

### Option C (chosen) — `[calibrate]` owns the numerics; `[benchmark]` depends on `"councilagent[calibrate]"`

```toml
benchmark = [
    "councilagent[calibrate]",
    "datasets>=2.19",
    "mlflow>=2.14",
    "statsmodels>=0.14",
    "hydra-core>=1.3",
]
calibrate = [
    "numpy>=1.26",
    "scipy>=1.13",
    "scikit-learn>=1.5",
]
```

Verified at branch creation:
- `uv sync --extra calibrate` resolves `numpy 2.4.4`, `scipy 1.17.1`,
  `scikit-learn 1.8.0`.
- `uv sync --extra benchmark` resolves the same numeric stack
  *transitively* plus `datasets`, `mlflow`, `statsmodels`, `hydra-core`.
- Existing test suite (897 passed, 25 skipped) is unchanged.

## Consequences

**Positive:**

- `council/calibrate/` is now self-describing under the L3-only
  `[calibrate]` extra. The architecture rules' §"Forbidden imports" intent
  is honoured at the dependency-graph level, not just at the import-edge
  level.
- The four W3 calibrators (`JSDCalibrator` in PR1, `MUSECalibrator` in PR2,
  `PrivilegedKnowledgeCalibrator` in PR3, `IsotonicCalibrator` in PR4) each
  declare `[calibrate]` as their install dependency naturally, with no
  cross-reference to `[benchmark]`.
- A user who only wants L3 calibration (e.g., for a downstream BAF
  re-scoring pipeline that does not need MLflow tracking) can install
  `councilagent[calibrate]` and skip the ~200 MB of `datasets`/`mlflow`
  weight.
- One source of truth for the numpy/scipy/sklearn version pins; no drift
  between extras.

**Neutral:**

- `[benchmark]` users see no behavioural change. Transitive resolution
  delivers the same numeric stack to existing `evaluation/` and
  `experiments/` callers.
- The `[full]` extra (line 79 of `pyproject.toml`) already includes
  `[benchmark]`, so it transitively includes `[calibrate]` — no edit
  needed.

**Negative:**

- New developers must remember that L3 work installs via
  `--extra calibrate`, not `--extra benchmark`. The cross-chat handoff
  context in `specs/w3-calibration.md` calls this out, and the
  re-exported PEP-508 spec gives a graceful degradation path:
  `--extra benchmark` still works for legacy muscle memory.
- One additional extra in `pyproject.toml` (10 → 11). Negligible
  inventory cost.

## References

- `pyproject.toml` lines 33-42 (`[benchmark]`) and 60-71 (`[calibrate]`) —
  the implementation
- `specs/w3-calibration.md` §"Resolved decisions" Q1 — the user
  authorisation
- `COUNCILAGENT_NS_MASTER_PLAN.md §7 W3` — the four concrete calibrators
  that need this extra
- `.claude/rules/architecture.md §"Forbidden imports"` — the layering rule
  that motivates the split
- `.claude/rules/architecture.md §"L3 calibrate"` — the layer's
  responsibilities
- `docs/adr/0008-calibrator-abc-location.md` — the W2 ADR that placed
  `Calibrator` ABC + `IdentityCalibrator` in `council/calibrate/base.py`;
  this ADR is the natural sequel for the dependency stack
