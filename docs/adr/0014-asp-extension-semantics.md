# ADR-0014: ASP-backed extension semantics for the W2 QBAF

## Status

Accepted.

## Date

2026-05-01

## Context

W2/PR8 ships `council/symbolic/argue/asp_backends.py`, the `[argue-asp]`
extra's deliverable. The bible §6.3 names this:

> `asp_backends.py     # Optional: extension semantics (preferred/stable/grounded) via clingo`

Three Dung 1995 extension semantics ("On the acceptability of arguments
and its fundamental role in nonmonotonic reasoning, logic programming and
n-person games", AIJ 77, in `papers/3 --- argumentation/`):

- **Grounded extension**: the unique least fixed point of the Dung
  characteristic function — the smallest admissible set under set
  inclusion.
- **Preferred extensions**: the maximal admissible sets (multiple may
  exist; non-empty for any AAF).
- **Stable extensions**: complete extensions where every argument *not*
  in the extension is attacked by something in the extension. May be
  empty for some AAFs.

Three design questions arise.

## Decision

**Q1 — Backend choice for each extension type.**

- **Grounded**: pure-Python fixed-point iteration. The Dung characteristic
  function `F(S) = { a | every attacker of a is attacked by some member
  of S }` is a monotone function on a finite lattice; iterating from `∅`
  reaches the least fixed point in O(|args|·|attacks|) steps. Clingo is
  unnecessary for the grounded case and would only add an external
  binary call without computational benefit.
- **Preferred** + **Stable**: clingo. Both require enumeration over
  models (one ASP grounding produces multiple answer sets, one per
  extension). Pure-Python implementations would re-derive the
  Aspartix encoding from scratch and lose the well-tested clingo backend.
  The Egly-Gaggl-Woltran 2010 ASP encoding (the "Aspartix" encoding) is
  the canonical reference; we adapt it with clingo's stable-model
  enumeration.

**Q2 — Scope: extension semantics over the attack subgraph only.**

Dung 1995's framework operates on `(Args, Att)` pairs: arguments and
binary attack relations. The W2 QBAF carries `attacks: tuple[Attack,
...]` and `supports: tuple[Support, ...]`. **Extension semantics in
PR8 are computed over the attack subgraph only**, ignoring supports.
Rationale:

- Dung extensions are formally defined over the attack relation. There
  is no canonical extension semantics for bipolar AAFs that uniformly
  generalises Dung; multiple research papers (Cayrol-Lagasquie-Schiex
  2009, Amgoud-Ben-Naim 2018) propose competing extensions.
- The W2 *gradual* semantics (DF-QuAD, QE, Ebs, Strategic-Coupled) are
  the headline confidence-producing path; they consume both attacks
  AND supports. The ASP-backed extension semantics in PR8 are
  complementary — they classify arguments into "in/out" sets, which is
  useful for the demo (visualising the preferred extension) and for W6
  ILP rule mining (target predicates).
- This matches the bible §6.3 phrasing: "extension semantics
  (preferred/stable/grounded)" — the classical Dung trio over attacks.

The architecture-rules audit is unchanged: `asp_backends.py` imports
only `baf` + stdlib + (lazily) `clingo`.

**Q3 — Withdrawn arguments.**

Withdrawn arguments are excluded from the ASP encoding (and from the
fixed-point iteration). They are not "in play" for extension purposes,
matching the gradual-semantics convention from ADR-0010 Q2.

**Q4 — Self-attack detection scope.** ADR-0007's deferral remains in
effect. PR8 ships extension semantics ONLY. Self-attack detection
(when a Propose's claim contradicts its own evidence for ARITH/FOL
domains) is deferred again — implementing it would require either:

- A `ToolClient.check_consistency` API + MCP server config (significant
  W0/W7 infrastructure), per ADR-0007's stated path.
- Direct Z3 import in `argue/`, which violates `argue/ → tools.py`
  routing per the architecture rules.

PR8's `asp_backends.py` does NOT introduce a `argue/asp_backends.py →
tools.py` approved exception. ADR-0007's "Negative" consequences
section ("Until PR8 ships, ...") still applies to a future post-W2 PR.

## Alternatives Considered

### Q1 alt — Use clingo for grounded too (uniform-backend story)

Force clingo for all three; raise `ImportError` from
`grounded_extension(qbaf)` when clingo is missing.

**Rejected.** Grounded is a fixed-point computation that runs in
O(|args|·|attacks|) without external dependencies. Forcing clingo on
the no-extras path would deny users a perfectly good extension
semantics for an unrelated optional dep. The ADR documents the split:
grounded is pure-Python (always available); preferred + stable require
`[argue-asp]`.

### Q1 alt — Use pure-Python for all three

Implement Aspartix-style enumeration in Python.

**Rejected.** Clingo is a mature, well-tested ASP solver maintained by
the Potsdam group (Gebser et al.). Re-implementing stable-model
enumeration in Python would require significant correctness validation
and would not match clingo's performance on graphs with many
extensions. The `[argue-asp]` extra is a clean opt-in.

### Q2 alt — Define extension semantics over the bipolar graph

Use Cayrol-Lagasquie-Schiex's bipolar admissibility (which threads
support through complex-attack chains).

**Rejected.** Multiple research papers propose competing definitions
of bipolar admissibility; there is no consensus. Adopting one would
make PR8 an opinionated take on a research debate that's not central
to W2's deliverable. The classical Dung trio over the attack subgraph
is uncontroversial and standard. If a future workstream needs bipolar
extensions, that's a research-paper deliverable, not a W2 mechanism.

### Q4 alt — Implement self-attack detection in PR8

Add a small Z3-or-clingo self-attack detector now, before W7 builds
the MCP server infrastructure.

**Rejected.** Self-attack detection requires symbolic reasoning over
claim+evidence content. Implementing this without the proper
`tools.py::ToolClient` indirection would either:

- Violate ADR-0007's routing decision (direct Z3 import in `argue/`).
- Add a Python-level claim parser that's heuristic and brittle (the
  evidence-count alternative rejected in ADR-0006).

The deferral remains. The `is_complete()` clause in PR6 (Patch E)
already verifies receipt structure for the headline path; self-attack
detection would only refine the edge cases.

## Consequences

**Positive:**

- Three classical extension semantics are available for the demo and
  for downstream W6 ILP rule mining target predicates.
- The split (grounded pure-Python; preferred/stable clingo) is honest
  about dependencies.
- Egly-Gaggl-Woltran 2010 ASP encoding is well-known to KR / AAAI
  reviewers; P2 (AAAI 2027) reviewers will recognise the encoding.
- The `[argue-asp]` extra now has a real, tested deliverable rather
  than a placeholder.

**Neutral:**

- Both backends respect the same `withdrawn=True` exclusion convention
  established in ADR-0010 Q2.
- The fixed-point iteration for grounded handles cycles correctly (the
  least fixed point is well-defined for any finite AAF).

**Negative:**

- Self-attack detection remains deferred. ADR-0007's "Negative" clause
  about Proposes contradicting evidence still applies.
- ASP backends operate on the attack subgraph only — supports do not
  influence extension membership. Documented in module docstring.

## References

- `council/symbolic/argue/asp_backends.py` — implementation (W2/PR8)
- `papers/3 --- argumentation/Dung 1995 ... (AIJ).pdf` — extension
  semantics: grounded (§3, fixed-point of characteristic function),
  preferred (§3, maximal admissible), stable (§4)
- Egly, Gaggl, Woltran. *Answer-Set Programming Encodings for
  Argumentation Frameworks*. Argument and Computation 2010 — the
  "Aspartix" encoding. Adapted for clingo's stable-model enumeration.
  (Not in `papers/3`; standard reference cited in P2's bibliography.)
- `docs/adr/0007-self-attack-deferred.md` — sister ADR; PR8 does not
  fulfil the self-attack-detection promise.
- `docs/adr/0010-df-quad-design-choices.md` — withdrawn-argument
  exclusion convention (Q2).
- `pyproject.toml` `[argue-asp]` extra — `clingo>=5.7` (5.8.0 as of
  2026-05-01).
