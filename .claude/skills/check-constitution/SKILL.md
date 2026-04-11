---
name: check-constitution
description: Runs a fast, scripted audit of the current working tree against the CouncilAgent Constitution. Use when the user says "check constitution", "audit", or "/check-constitution". Reports blockers with file:line citations. Faster than invoking the constitution-reviewer subagent — use the subagent for a nuanced review, this skill for a rapid pre-commit gate.
---

# check-constitution

A rapid, grep-driven audit that pins the most common Constitution violations. Complements (does not replace) the `constitution-reviewer` subagent.

## Procedure

1. Run these greps in parallel. Each one that returns a match is a BLOCKER.

   ```bash
   # §3 — layering: core must have no framework imports
   rg -n '^(import|from)\s+(langgraph|hydra|mlflow|opentelemetry|langchain)' council/core.py council/agent.py council/policy.py 2>/dev/null

   # §3 — layers must not cross-import
   rg -n '^from council\.(protocol|aggregation|ranking|topology) import' council/topology.py council/protocol.py council/ranking.py council/aggregation.py 2>/dev/null

   # §4 — hardcoded models in aggregation (MetaJudge must inject)
   rg -n '"(openai|anthropic|google|openrouter)/' council/aggregation.py council/topology.py council/protocol.py 2>/dev/null

   # Issue 1 — chairman smuggling
   rg -n 'agent_ids\[0\]|chairman' council/topology.py 2>/dev/null

   # §4 — raw Counter on response content
   rg -n 'Counter\(.*\.content' council/ 2>/dev/null

   # §9 — substring answer match
   rg -n 'if\s+\w+\s+in\s+\w+:.*# accuracy|g\s+in\s+p' evaluation/metrics.py 2>/dev/null

   # Style — print statements
   rg -n '\bprint\(' council/ evaluation/ 2>/dev/null

   # Style — silent except
   rg -n 'except\s+Exception\s*:\s*pass' council/ evaluation/ 2>/dev/null

   # §10 — agent_id leaked into protocol prompts
   rg -n '\{.*agent_id.*\}|resp\.agent_id' council/protocol.py 2>/dev/null
   ```

2. Collect all matches. Group into BLOCKERS (§3, §4, Issue 1, §10) and WARNINGS (style, substring match).

3. Report in this format:

   ```
   ## Constitution Check — <branch>

   BLOCKERS: <N>
   - council/topology.py:45 — "agent_ids[0]" — Issue 1 (chairman)
   - ...

   WARNINGS: <N>
   - ...

   RESULT: <BLOCK | PASS>
   ```

4. If `council/` does not yet exist (early project), report `RESULT: PASS (council/ not created yet)` and exit.

## When NOT to use this
- Nuanced architectural review → use `constitution-reviewer` subagent instead
- Checking test coverage or correctness → this skill only pattern-matches
