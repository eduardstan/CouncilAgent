---
name: check-constitution
description: Runs a fast, scripted audit of council/ against the 12-principle Constitution (in .claude/CLAUDE.md). Complements the constitution-reviewer subagent. Use as a pre-commit gate for council/ changes.
---

# check-constitution

A rapid, grep-driven audit pinning the most common Constitution violations. Complements (does not replace) the `constitution-reviewer` subagent.

## Procedure

Run these greps in parallel. Each match in the BLOCKER section is a hard fail.

```bash
# §3 — typed protocol enforcement (Aggregator must take Trace, not list[AgentResponse])
rg -n 'Aggregator.*responses:\s*list\[AgentResponse\]' council/

# §3 — peer-layer cross-imports (forbidden)
rg -n '^from council\.(symbolic\.argue|calibrate|cascade|evolve|symbolic\.verify|symbolic\.ilp) import' \
   council/symbolic/argue/ council/calibrate/ council/cascade/ council/evolve/ \
   council/symbolic/verify/ council/symbolic/ilp/ 2>/dev/null

# §4 — typed Move enforcement
rg -n '\bcontent:\s*str\b' council/context.py
rg -n '\bresponse\.content\b' council/core.py council/agent.py council/policy.py 2>/dev/null

# §5 — plurality-fraction confidence (banned)
rg -n 'winner_count\s*/\s*(len|total)' council/
rg -n 'confidence\s*=\s*\d+\s*/\s*\d+' council/

# §8 — framework imports in core (extras-guarded only)
rg -n '^(import|from)\s+(langgraph|hydra|mlflow|opentelemetry|langchain)' \
  council/core.py council/agent.py council/policy.py \
  council/dialect/ council/calibrate/ council/cascade/ council/evolve/ 2>/dev/null

# §11 — receipt completeness
rg -n 'ProvenanceReceipt\b' council/

# §12 — interventions registered for each property
rg -n 'class.*\(Property\):' council/symbolic/verify/properties.py 2>/dev/null
rg -n 'class.*\(Intervention\):' council/symbolic/verify/interventions.py 2>/dev/null

# Argumentation layer cleanliness — no LLM extraction in the headline path
rg -n 'model_client|acompletion' council/symbolic/argue/builders.py 2>/dev/null \
  | rg -v 'argument-mining-fallback'

# Hardcoded model names in cascade strategies
rg -n '"(openai|anthropic|google|openrouter)/' council/cascade/ 2>/dev/null

# Round-parity in aggregation (banned in NS — D13)
rg -n 'round_index\s*%\s*2' council/symbolic/argue/ 2>/dev/null

# Style — print, silent except, mutable defaults
rg -n '\bprint\(' council/ evaluation/ 2>/dev/null
rg -n 'except\s+Exception\s*:\s*pass' council/ evaluation/ 2>/dev/null
```

## Output

Group findings:
- **BLOCKERS** — §3, §4, §5, §8, §11, §12 violations.
- **WARNINGS** — argumentation layer dirtying, hardcoded model names, round-parity.
- **NITS** — style.

Then:

```
## NS Constitution Check — <branch>

BLOCKERS: <N>
- <file>:<line> — <quoted snippet> — <which §> — <fix sketch>

WARNINGS: <N>
- ...

NITS: <N>
- ...

RESULT: <BLOCK | PASS>
```

If `council/` does not yet have NS layout (e.g. on `main` before substrate landed), report `RESULT: PASS (NS layout not created yet)` and exit.

## When NOT to use this

- Nuanced architectural review → use `constitution-reviewer-ns` subagent.
- Theorem audit → use `theorem-checker` agent.
- Argumentation builder review → use `qbaf-reviewer` agent.
