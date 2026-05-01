# Spec: W3 — Calibrated Disagreement (L3)

**Branch:** `council-ns` → feature branches `feature/ns-w3-*`
**Milestone:** M2 (end Jul 2026) — same milestone as W2; **AAAI 2027 deadline ~Aug 1 2026 (~12 weeks from 2026-05-01)**
**Workstream:** W3 (L3 only — composes onto W0 substrate + W1 spine + W2 argumentation)
**Paper coupling:** P2 *Strategic Gradual Argumentation* (calibrator-fed BAF base scores) + P3 *Quality-Diversity over Deliberation Behaviour* (calibration as a behavioural-descriptor signal). See [`COUNCILAGENT_NS_MASTER_PLAN.md`](../COUNCILAGENT_NS_MASTER_PLAN.md) §9.
**Status:** READY TO START — Calibrator ABC stub already shipped in W2/PR1 ([ADR-0008](../docs/adr/0008-calibrator-abc-location.md))

---

## Objective

Build the L3 calibration layer for `CouncilAgent-NS`: four concrete `Calibrator` subclasses that turn raw model confidences into calibrated confidences, plus two termination strategies (`JSDDivergenceTermination`, `ConFreezeTermination`) that hook into `CompositeTermination`.

The Calibrator ABC stub already exists at [`council/calibrate/base.py`](../council/calibrate/base.py) (W2/PR1, ADR-0008). W3 fills:

- `council/calibrate/jsd.py` — Jensen-Shannon divergence calibrator
- `council/calibrate/muse.py` — MUSE subset-ensemble divergence (Kruse et al. 2025)
- `council/calibrate/privileged.py` — Per-domain privileged-knowledge weights from `TaskProfile`
- `council/calibrate/isotonic.py` — Temperature-scaled isotonic regression

Plus the W3 termination strategies in `council/termination.py`.

**Why this matters.** Constitution §5: calibrated confidence is the council's unique value. Without W3, the only confidence signal is the W2 `BAFMarginConfidence` (margin between winner and runner-up), which is a graph-structural signal, not a calibration-based one. P2's P3 reviewer-bait — "ECE ≤ 0.05 vs legacy 0.20" — requires W3.

**Users:**
- The W2 `ArgumentationAggregator` (calibrator-fed BAF base scores via `build_qbaf(trace, calibrator=...)`)
- The future W5 QD descriptors (calibration accuracy as a behavioural axis)
- The future Streamlit demo (live ECE display)

**Success:**
- Every W3 acceptance criterion from `COUNCILAGENT_NS_MASTER_PLAN.md §7 W3` is checked off
- `mypy --strict` passes on `council/calibrate/`
- All four calibrators have positive + negative trace tests
- An end-to-end `run_council()` test with `JSDCalibrator` produces `JSDConfidence` (the Constitution §5 hierarchy: `MonitorVerdictConfidence > BAFMarginConfidence > JSDConfidence > CopelandConfidence`)

---

## Tech Stack

- Python 3.11+, `asyncio`, `mypy --strict`, `ruff`
- `pytest` + `pytest-asyncio` (mode = `auto`)
- **`numpy + scipy + scikit-learn`** — required for L3. They live in the `[benchmark]` extra (lines 38-44 of `pyproject.toml`). W3 should add a new `[calibrate]` extra OR reuse `[benchmark]` — TBD in Slice A.
- **No model calls in unit tests.** ECE measurements use cached fixture data; the AAAI/AAMAS-grade ECE numbers will require real LLM runs, gated behind `RUN_INTEGRATION=1`.

---

## Commands

```bash
# Full test suite
uv run pytest tests/

# W3-only tests
uv run pytest tests/calibrate/

# Type-check
uv run mypy council/

# Lint
uv run ruff check council/ tests/

# Install calibrate extra (numpy + scipy + scikit-learn)
uv sync --extra dev --extra calibrate
# OR re-use benchmark extra if W3 doesn't get its own:
uv sync --extra dev --extra benchmark
```

---

## Project Structure

Files created by W3 (all new unless marked **MODIFIED**):

```
council/calibrate/
├── __init__.py                  MODIFIED — re-exports + __all__
├── base.py                      EXISTS (W2/PR1; ADR-0008)
├── jsd.py                       NEW — JSDCalibrator + jsd_divergence helper
├── muse.py                      NEW — MUSECalibrator (Kruse et al. 2025)
├── privileged.py                NEW — PrivilegedKnowledgeCalibrator
└── isotonic.py                  NEW — IsotonicCalibrator (sklearn IsotonicRegression)

council/termination.py           MODIFIED — add JSDDivergenceTermination,
                                            ConFreezeTermination

tasks/profiles.py                MODIFIED — privileged-knowledge default weights
                                            per domain (factual 5%, math 0%, ...)

tests/calibrate/                 NEW directory (mirrors council/calibrate/)
├── __init__.py
├── test_jsd.py                  determinism + closed-form n=2 uniform vs Dirac
├── test_muse.py                 Kruse et al. 2025 reference numbers (synthetic toy)
├── test_privileged.py           per-domain weights match DOCX table
├── test_isotonic.py             ECE on cached GSM8K subset drops below 0.05
└── test_terminations.py         JSDDivergenceTermination + ConFreezeTermination

tests/integration/
└── test_calibration_real_models.py    NEW — gated RUN_INTEGRATION=1; real LLM ECE

docs/adr/
└── 0015-calibrate-extra-or-benchmark.md   NEW (Slice A) — pyproject extra decision
```

---

## PR Sequence (master plan §7 W3)

| # | Branch slug | Deliverable | ADR? |
|---|---|---|---|
| 1 | `ns-w3-jsd` | `JSDCalibrator` — Jensen-Shannon divergence over `list[dict[str, float]]`; closed-form n=2 uniform vs Dirac test; `JSDConfidence` integration into `CouncilResponse` via `Aggregator.aggregate` (when `JSDCalibrator` is wired into `build_qbaf`) | Maybe ADR-0015 (calibrate extra split from benchmark) |
| 2 | `ns-w3-muse` | `MUSECalibrator` — subset-ensemble divergence; matches Kruse et al. 2025 reference values on a committed synthetic toy fixture | No |
| 3 | `ns-w3-privileged` | `PrivilegedKnowledgeCalibrator` — per-domain (`ClaimDomain.ARITH`, `FOL`, `CODE`, `FREE`, `LTLF`) confidence weights from `TaskProfile`; defaults match DOCX table (factual 5%, math 0%, coding partial) | No (table is in master plan) |
| 4 | `ns-w3-isotonic` | `IsotonicCalibrator` — sklearn `IsotonicRegression`; ECE on cached GSM8K split ≤ 0.05 | No |
| 5 | `ns-w3-terminations` | `JSDDivergenceTermination(threshold=0.05)`, `ConFreezeTermination(window=5)`; both plug into `CompositeTermination` | No |

**Total estimate**: ~3-4 weeks if running in parallel with theorem revisions; ~2-3 weeks if focused.

---

## Required contracts (architecture rules already freeze these)

```python
# council/calibrate/base.py — EXISTS (W2/PR1)
class Calibrator(ABC):
    @abstractmethod
    def calibrate(
        self, raw_confidence: float, agent_id: str, claim_domain: ClaimDomain
    ) -> float: ...

# council/calibrate/jsd.py — TO BE WRITTEN (W3/PR1)
class JSDCalibrator(Calibrator):
    """Jensen-Shannon divergence over per-agent response distributions.
    The calibrated confidence reflects how much consensus exists across
    agents — high JSD = high disagreement = low calibrated confidence."""
    def compute(self, distributions: list[dict[str, float]]) -> float:
        """Return JSD ∈ [0, 1] over the agent response distributions."""
```

The `Calibrator.calibrate(raw_confidence, agent_id, claim_domain)` signature is FROZEN per `.claude/rules/architecture.md` §"Required contracts". W3 must not change it.

---

## Approved exception (architecture rules already permits)

`council/symbolic/argue/aggregator.py → council/calibrate/jsd.py` (Approved Exception #1) is already declared in `.claude/rules/architecture.md`. W3 fulfills it: PR1 (`ns-w3-jsd`) lights up the import path that PR6 of W2 (`ArgumentationAggregator.__init__(calibrator=...)`) already prepared.

---

## Boundaries

**Always do:**
- Run `uv run mypy council/` before every PR — zero errors required
- `JSDConfidence`, not raw `float`, when wiring into `CouncilResponse`
- Cache GSM8K test fixtures under `tests/calibrate/fixtures/` — no real model calls in unit tests
- Withdrawn arguments: out of scope for L3 (handled at L2 per ADR-0010 Q2)

**Ask first:**
- Adding a new optional dep beyond what `[benchmark]` already provides
- Changing the `Calibrator` ABC signature (frozen by architecture rules)
- Modifying `council/symbolic/argue/builders.py` beyond passing through `calibrator.calibrate()`
- Changing `Confidence` union types in `council/context.py`

**Never do:**
- Import `council/symbolic/argue/` from `council/calibrate/` (only the *reverse* is permitted via Approved Exception #1)
- Call `ModelClient` from `council/calibrate/`
- Use the `[verify]` or `[argue-asp]` extras' deps inside `calibrate/`
- Use `numpy`/`scipy` outside `[benchmark]`/`[calibrate]` extras

---

## Acceptance criteria (master plan §7 W3 verbatim)

- [ ] `JSDCalibrator.compute(distributions: list[dict[str, float]]) → float` — tested against a closed-form for n=2 uniform vs Dirac
- [ ] `MUSECalibrator` — subset-ensemble divergence; matches Kruse et al. 2025 reference numbers on a synthetic toy
- [ ] `PrivilegedKnowledgeCalibrator` — per-domain weights from `TaskProfile`; defaults match the DOCX table (factual 5%, math 0%, coding partial)
- [ ] `IsotonicCalibrator` — temperature-scaled isotonic regression; ECE on a held-out GSM8K split drops below 0.05
- [ ] `JSDDivergenceTermination`, `ConFreezeTermination` plug into `CompositeTermination`

Plus the standard project gates:
- [ ] `uv run mypy council/` — 0 errors (strict)
- [ ] `uv run pytest tests/` — all green; ≥ 30 new tests under `tests/calibrate/`
- [ ] `uv run ruff check council/ tests/` — clean
- [ ] No new forbidden imports (no `argue/`-from-`calibrate/`; no model calls in `calibrate/`)
- [ ] `CouncilResponse` from a `JSDCalibrator`-wired `CouncilAgent.complete()` returns `JSDConfidence` (Constitution §5 hierarchy)

---

## Open questions (resolve in Slice A)

1. **`[calibrate]` extra vs reuse `[benchmark]`?** L3 needs numpy + scipy + sklearn. They're already in `[benchmark]` (line 38-44 of pyproject.toml), but `[benchmark]` is "Bootstrap, Wilcoxon, AIPW, Bradley-Terry, mixed-effects" — orthogonal to calibration. ADR-0015 should resolve.
2. **GSM8K fixture caching strategy?** Real LLM responses on GSM8K subset → cache via `pickle` or commit `.json`? The Isotonic test needs deterministic ECE. Resolve in PR4.
3. **MUSE reference numbers?** Kruse et al. 2025 paper — does the user want the exact paper-reported numbers as the test target, or a synthetic-toy approximation? Resolve in PR2.
4. **`ConFreeze` window default?** Bible says 5; spec is silent. Default to 5; configurable.

---

## Resolved decisions (2026-05-01)

This section captures the user's resolutions to the five open questions surfaced by the workstream-planner. They override any ambiguity above.

1. **Q1 — `[calibrate]` extra split: APPROVED.** Create a new `[calibrate]` extra in `pyproject.toml` for `numpy + scipy + scikit-learn`. Have `[benchmark]` transitively include `[calibrate]`. Rationale: keeps `council/calibrate/` self-describing under `.claude/rules/architecture.md` §"Forbidden imports" (L3 must not depend on `[benchmark]` semantics, which are evaluation-side: Bootstrap/AIPW/Bradley-Terry). ADR-0015 captures this in PR1 (`feature/ns-w3-jsd`) per the workstream-planner output.
2. **Q2 — MUSE reference numbers: REPRODUCE EXACTLY.** PR2 (`feature/ns-w3-muse`) tests must match the numbers reported in [`papers/2 --- calibration and disagreement/Kruse et al. 2025 "Simple Yet Effective: An Information-Theoretic Approach to Multi-LLM Uncertainty Quantification" (EMNLP; arXiv:2507.07236).pdf`](../papers/) on the toy distributions defined in §3 of that paper. We are scientists; if the paper reports an exact subset-divergence value for a 3-model uniform-vs-skewed configuration, the unit test asserts that value to within a documented numerical tolerance (1e-6 by default). Synthetic-toy approximation is rejected.
3. **Q3 — Real-LLM fixture sources: OpenRouter SLMs.** PR4 (`feature/ns-w3-isotonic`) and `tests/integration/test_calibration_real_models.py` use OpenRouter-routed SLMs. The user's `OPENROUTER_API_KEY` lives in the private (untracked) `.env` at the repo root. **Slate updated 2026-05-01** during PR4: the originally proposed free-tier candidates (`gemma-3-27b-it:free`, `llama-3.1-8b-instruct:free`, `qwen-2.5-7b-instruct:free`) were abandoned because (a) the Llama and Qwen IDs returned `404 No endpoints found` from OpenRouter and (b) the surviving Gemma free model did not return logprobs and rate-limited on a 32-question probe. The committed paid slate is: `openrouter/openai/gpt-4.1-nano`, `openrouter/qwen/qwen3.5-flash-02-23`, `openrouter/google/gemini-2.5-flash-lite`. The exact slate is recorded in each generated fixture's `models` field.
4. **Q4 — `ConFreeze` window default: 5.** Matches `COUNCIL_NS_PLAN.md` and Anonymous 2026 *ConFreeze* ([`papers/2 --- calibration and disagreement/Anonymous 2026 "ConFreeze: Selective Multi-Model Debate through Consensus Freezing" (Preprint; OpenReview:PrqXuAS4BZ).pdf`](../papers/)). The window is configurable via `ConFreezeTermination(window=5)`; tests must cover both `window=3` (faster freeze) and `window=5` (default).
5. **Q5 — PR5 split: NO.** Keep PR5 as a single `feature/ns-w3-terminations` deliverable shipping both `JSDDivergenceTermination` and `ConFreezeTermination`. The user is confident in the AAAI 2027 timeline and does not want deadline pressure to fragment the L3 termination layer.

**Implementation note (PR1, 2026-05-01).** `jsd_divergence(distributions)` for n≥3 returns the *mean of pairwise JSDs* over the union support (not the Lin-1991 n-mixture form). This is the simplest correct generalisation that ships from `scipy.spatial.distance.jensenshannon` directly; the proper subset-ensemble (Kruse et al. 2025) version is the responsibility of `MUSECalibrator` / `muse_greedy` (PR2). Documented in `council/calibrate/jsd.py` module docstring.

**Literature ground truth.** Where the user is silent on a numerical or design parameter, defer to the corresponding paper in `papers/2 --- calibration and disagreement/`:
- JSD baseline: any standard reference; the closed-form n=2 uniform-vs-Dirac value is `JSD = ln(2)` in nats (equiv. 1.0 normalised).
- MUSE: Kruse et al. 2025 (EMNLP; arXiv:2507.07236).
- Privileged knowledge: Anonymous 2026 *Masked by Consensus* (OpenReview: du3ZBA8Z3Z) — the per-domain weight table.
- ConFreeze: Anonymous 2026 (OpenReview: PrqXuAS4BZ) — window semantics + freeze rule.
- Isotonic / ECE: any standard temperature-scaling reference; the target `ECE ≤ 0.05` is fixed by `COUNCILAGENT_NS_MASTER_PLAN.md` §7 W3.

---

## Cross-chat handoff context (read this first)

The new chat session for W3 should know:

1. **W2 is complete** on `council-ns` (commits `dd1ebf1..d191584`, 9 PRs, ADRs 0006-0014, ~755 new tests).
2. **The Calibrator ABC + IdentityCalibrator are already shipped** at [`council/calibrate/base.py`](../council/calibrate/base.py) (W2/PR1; ADR-0008). W3 fills concretes; do not modify the ABC.
3. **`build_qbaf(trace, calibrator=None)`** ([`council/symbolic/argue/builders.py`](../council/symbolic/argue/builders.py)) already accepts a `Calibrator | None`. When None, it uses `Propose.confidence` directly. When given, it calls `calibrator.calibrate(propose.confidence, propose.agent_id, propose.claim.domain)`. W3's PR1 (JSD) will plug here.
4. **`ArgumentationAggregator.__init__(calibrator=None)`** ([`council/symbolic/argue/aggregator.py`](../council/symbolic/argue/aggregator.py)) already accepts a Calibrator and threads it to `build_qbaf`.
5. **The Confidence union** ([`council/context.py`](../council/context.py)) has `JSDConfidence`, `BAFMarginConfidence`, `MonitorVerdictConfidence`, `CopelandConfidence`. JSD-derived confidence in W3 should produce `JSDConfidence`. Hierarchy: `MonitorVerdictConfidence > BAFMarginConfidence > JSDConfidence > CopelandConfidence` (Constitution §5).
6. **Architecture rules** ([`.claude/rules/architecture.md`](../.claude/rules/architecture.md)) — read these before PR1. The L3 contract is frozen.
7. **Operating skills**: `/spec-driven-development` (already done — this file), `/git-workflow-and-versioning`, `/planning-and-task-breakdown`, `/incremental-implementation`, `/test-driven-development`, `/documentation-and-adrs`. Same workflow as W2.
8. **Memory**: see `~/.claude/projects/-home-eduard-Dropbox-Projects-CouncilAgent/memory/MEMORY.md` for project status, theorem audit findings, and AAMAS readiness verdict.
9. **Theorem audit findings** (relevant to P2): T4-T7 still need revision (master-plan-§9 P2 deadline is AAAI 2027 ~Aug 1 2026). The W3 work feeds P2 alongside theorem revisions.
10. **Release tag status**: tagged `v0.2.1` at end of W2; `v0.3.0` reserved for "M2 complete" (P1+P2 ready to submit).

Open this file first in the new chat for W3, then proceed with `/spec-driven-development` to refine, or jump straight to PR1 with `/incremental-implementation`.
