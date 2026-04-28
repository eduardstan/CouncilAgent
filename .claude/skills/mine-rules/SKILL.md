---
name: mine-rules
description: Runs Popper or ILASP4 over a labelled-trace bundle in experiments/traces/<slug>/. Outputs an ASP rule set + the MCMAS verification report. Use in the W6 / P5 pipeline.
---

# mine-rules

Mine dialogue protocol rules from a labelled trace bundle and re-verify them.

## Inputs
- `<slug>` — the trace-bundle directory under `experiments/traces/`. Must contain `positive.json`, `negative.json`, `background.pl`.
- Optional: `--miner=popper|ilasp` (default: `popper`).

## Procedure

1. **Prerequisite check.** `council/symbolic/ilp/{popper,ilasp,verify_learned}.py` must exist (W6 prereq); the chosen binary (`popper` or `ilasp`) must be on PATH (extras `[ilp]`). If not, stop.
2. **Validate bundle.** Confirm `positive.json`, `negative.json`, `background.pl` exist and parse.
3. **Run the miner:**
   ```bash
   uv run python -m council.symbolic.ilp.popper \
       --positive experiments/traces/<slug>/positive.json \
       --negative experiments/traces/<slug>/negative.json \
       --background experiments/traces/<slug>/background.pl \
       --output experiments/traces/<slug>/rules.lp
   ```
   (or the ILASP equivalent.)
4. **Verify the induced rules.** Pipe `rules.lp` into `verify_learned.py`; for each L1 property in `properties.py`, confirm the induced protocol satisfies it via MCMAS.
5. **Emit a report:**
   ```
   ## Rule mining — <slug>
   
   ### Miner
   <popper|ilasp>
   
   ### Induced rules
   <rules.lp content>
   
   ### MCMAS verification per property
   - EventuallyDecide: ⊤
   - NoPrematureConsensus: ⊤
   - ...
   
   ### Suggested ProtocolAutomaton subclass name
   <Name>Automaton
   
   ### Next step
   `/new-protocol-automaton <Name>` then plug in the learned rules.
   ```

## Invariants enforced
- Only verified rules are promoted to a `ProtocolAutomaton` subclass (T12 soundness).
- The miner runs against frozen positive/negative bundles (no model calls).

## Reject criteria
- Bundle missing required files.
- Induced rules fail any L1 property (report failure, do not promote).
