# Verifying — how to add a new LTL_f property

This is the contributor guide for the W1 verification spine
(`council/symbolic/verify/`). Read it when you want to add a new monitor
that runs over `Trace.to_events()` events and reports a Verdict
(`TOP` / `BOTTOM` / `UNKNOWN`) for a deliberation invariant.

> **Audience.** Researchers extending the named-property library, paper
> authors mechanising a new theorem, or contributors generalising the
> existing 10 properties (see [`council/symbolic/verify/properties.py`](../council/symbolic/verify/properties.py)).
>
> **Prerequisites.** Read [`docs/theory.md`](theory.md) for T1–T3 and
> [`docs/installation.md`](installation.md) for SPOT / MCMAS / NuSMV
> install. The constitutional and architectural rules in
> [`.claude/CLAUDE.md`](../.claude/CLAUDE.md) and
> [`.claude/rules/architecture.md`](../.claude/rules/architecture.md) apply.

## The four-step recipe

### 1. Write the LTL_f formula against the `to_events()` schema

Atoms in your formula must match the keys emitted by `Trace.to_events()`
([`council/dialect/trace.py`](../council/dialect/trace.py)):

| Key | Type | Meaning |
|---|---|---|
| `force` | `str` | one of `"propose"`, `"challenge"`, ... |
| `agent_id` | `str` | move's emitting agent |
| `round_index` | `int` | move's round |
| `is_propose`, `is_challenge`, ..., `is_pass` | `bool` | one per Force value |
| `has_evidence` | `bool` | move's `Claim.evidence` is non-empty (Propose / Vote only) |
| `has_prior_challenge` | `bool` | any Challenge appears strictly earlier in the trace |
| `same_agent_concede_run_ge_3` | `bool` | this move and the two preceding same-agent moves are all Concede |

If you need a new atomic proposition, extend `to_events()` (the schema's
home) and update [ADR-0002](adr/0002-to-events-schema-freeze.md) +
[ADR-0003](adr/0003-to-events-w1-extension.md). Do NOT introduce
trace-context inspection in the property class itself — that breaks the
L0/L1 boundary.

### 2. Add the `Property` subclass to `properties.py`

```python
# council/symbolic/verify/properties.py
class MyNewInvariant(Property):
    """One-line description.

    Formal: G(...)  — what this property forbids/requires.
    Citation pointer to docs/theory.md or paper if applicable.
    """

    name: ClassVar[str] = "MyNewInvariant"
    formula: ClassVar[str] = "G(is_propose -> has_evidence)"

    def compile(self) -> LTL3Monitor:
        return make_monitor(parse(self.formula))
```

Then add it to `PROPERTY_REGISTRY` so YAML genomes can reference it by name:

```python
PROPERTY_REGISTRY: dict[PropertyName, type[Property]] = {
    cls.name: cls
    for cls in (
        EventuallyDecide, NoSycophancyCascade, ..., MyNewInvariant,
    )
}
```

If your property's formula is identical at L1 to another (e.g.
`ChallengeBeforeConsensus` and `RefutationReachable` share
`F(is_challenge && F(is_vote))` and only differ at L2), record this in
`L1_EQUIVALENCE_GROUPS`. If your `__init__` takes parameters (like
`BoundedRound(k=10)`), add the name to `L1_PARAMETERISED_PROPERTIES`.

### 3. Write at least one positive and one negative trace test

Tests live in `tests/symbolic/verify/test_properties.py`. Use the
`_fill(**flags)` helper to craft event dicts:

```python
def test_my_new_invariant_positive() -> None:
    m = MyNewInvariant().compile()
    final = _step_trace(m, [
        _fill(is_propose=True, has_evidence=True),
        _fill(is_vote=True, has_evidence=True),
    ])
    assert final is Verdict.UNKNOWN  # G never says TOP at runtime

def test_my_new_invariant_negative() -> None:
    m = MyNewInvariant().compile()
    final = _step_trace(m, [_fill(is_propose=True, has_evidence=False)])
    assert final is Verdict.BOTTOM
```

Three semantic gotchas to keep in mind for LTL3 verdicts:

- **Safety (`G(...)`)**: never reaches `TOP` at runtime (would require
  certainty over all future events). The "positive" test asserts `UNKNOWN`
  on a satisfying prefix; the "negative" asserts `BOTTOM` on a violating one.
- **Reachability (`F(...)`)**: never reaches `BOTTOM` at runtime. The
  "positive" test asserts `TOP` once the witness fires; the "negative"
  asserts `UNKNOWN` on a finite trace where the witness never appears.
- **Mixed `G/F` nesting** (e.g. `G(p -> F(q))`): both verdicts may be
  unreachable at runtime — the only honest assertion is `UNKNOWN`.

### 4. (Optional) Add an MCMAS-backed integration test

If you want external-verifier confirmation (recommended for theorems
cited in publications), add a gated test in
`tests/integration/test_mcmas_*.py`:

```python
@pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1" or not _mcmas_available(),
    reason="RUN_INTEGRATION=1 required and mcmas must be on PATH",
)
def test_mcmas_verifies_my_new_invariant() -> None:
    trace = _build_my_witness_trace()
    ispl = trace_to_ispl(trace, [parse("G(is_propose -> has_evidence)")],
                         agent_ids=("A", "B", "C"))
    rc, stdout, stderr = _run_mcmas(ispl)
    assert rc == 0
    assert "is FALSE in the model" in stdout  # or TRUE, depending on the trace
```

The ISPL emitter ([`council/symbolic/verify/ispl.py`](../council/symbolic/verify/ispl.py))
encodes a finite Trace as a deterministic Kripke structure for MCMAS.
LTL_f temporal operators are translated to CTL (`F → EF`, `G → AG`,
`X → EX`, `U → E[· U ·]`); the deterministic-trace encoding makes the
EF/AG forms equivalent to their LTL counterparts on the unique
computation path. See ADR-0005 for details on the manual-grounded
ISPL dialect we conform to.

## Constitution boundaries you cannot cross

- **§3 layer separation:** properties and monitors live in L1
  (`council/symbolic/verify/`). They MUST NOT call generation models,
  build deliberation prompts, or mutate the trace. Step over events
  emitted by `Trace.to_events()` only. The single approved cross-layer
  edge is `interventions.py → council/dialect/moves.py` (architecture
  exception 4).
- **§4 typed moves:** any intervention you add must inject typed `Move`
  subclasses (`Challenge`, `Question`, `Propose`, ...), never raw text.
- **§8 framework deps:** `import spot` MUST be guarded; the
  `make_monitor()` factory falls back to `ProgressionMonitor` when SPOT
  is unavailable.
- **§11 receipt completeness:** if your property is in the active genome
  for a run, its verdicts MUST appear in `ProvenanceReceipt.monitor_verdicts`
  (handled automatically by `LTLfMonitorTermination`).
- **§12 verifier intervention:** if you want your property to fire an
  intervention on `Verdict.BOTTOM`, configure it via
  `LTLfMonitorTermination(monitors=[MyProperty()], on_violation=ForceChallenge())`.

## Choosing a backend (`make_monitor()`)

The factory selects automatically. For a quick mental model:

| Formula shape | `PurePythonLTL3Monitor` | `ProgressionMonitor` | `SPOTMonitor` |
|---|---|---|---|
| Propositional (`a && b`) | ✅ | ✅ | ✅ (overkill) |
| `G(prop)` / `F(prop)` | ✅ | ✅ | ✅ |
| `X`, `U`, `W` | ❌ raises | ✅ | ✅ |
| Nested temporal (e.g. `G(p -> F(q))`) | ❌ raises | ✅ | ✅ |

`make_monitor()` returns `SPOTMonitor` when SPOT is installed and
`prefer_spot=True` (the default); otherwise `ProgressionMonitor`. The
`PurePythonLTL3Monitor` is the explicit entry point for the
safety+reachability fragment when you want a minimal-dependency,
fast-failing implementation.

## Where to file the work

| Slot | What |
|---|---|
| `council/symbolic/verify/properties.py` | new `Property` subclass + registry update |
| `tests/symbolic/verify/test_properties.py` | positive + negative tests |
| `council/dialect/trace.py` | only if a new atomic proposition is needed |
| `docs/adr/000N-...md` | only if the change is an architectural decision |
| `tests/integration/test_mcmas_*.py` | optional MCMAS-backed test |
| `docs/theory.md` | if the property is the subject of a theorem |

## Frequently asked

**Q: My property's formula has an `∃i. P(i)` quantifier. How do I express it?**

A: LTL_f is propositional — there is no `∃` over agents. Use the standard
propositional weakening: define a derived AP in `to_events()` that
captures the existential witness (`has_evidence` is the canonical example
for `∃i. evidenceFor(...)`). Document the weakening with an ADR.

**Q: I want my property to count occurrences (e.g., "no more than 3
challenges per round"). LTL_f doesn't count.**

A: Use a derived AP in `to_events()` that pre-computes the boolean
predicate (`same_agent_concede_run_ge_3` is the canonical example). The
monitor stays purely propositional in LTL_f.

**Q: My MCMAS run rejects the ISPL with a parse error.**

A: See ADR-0005 §"Bug 1" and §"Bug 2" — common pitfalls are CTL-keyword
collisions in identifiers (use the `agent_` prefix; handled
automatically by `_sanitise()`) and the absence of `!=` in the MCMAS
grammar. The MCMAS user manual at
<https://sail.doc.ic.ac.uk/software/mcmas/manual.pdf> §3.2 documents the
exact dialect.
