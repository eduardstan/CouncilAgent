---
name: new-descriptor
description: Scaffolds a new behavioural Descriptor subclass in council/evolve/descriptors.py plus tests. Use when the user says "add a new descriptor" or "/new-descriptor <Name>". Refuses descriptors that require generation-model calls or read raw text (NS Constitution §11) — descriptors must derive from L1+L2+L3 outputs only.
---

# new-descriptor

Scaffold a behavioural `Descriptor` (W5 / L5) for the QD archive.

## Inputs
- `<Name>` — PascalCase, ending in `Descriptor` (or descriptive). Examples: `DisagreementPersistenceDescriptor`, `QBAFDensityDescriptor`, `RoleEntropyDescriptor`, `EvidenceAnchorRateDescriptor`.

## Procedure

1. **Prerequisite check.** `council/evolve/descriptors.py` must exist (W5 prereq). If not, stop.
2. **Verify the descriptor source is symbolic.** It must derive from one of:
   - `result.receipt.qbaf` (L2 output)
   - `result.receipt.monitor_verdicts` (L1 output)
   - `result.receipt.confidence` (L3 output)
   - `result.round_history[i].move` (L0 typed substrate; `move.force`, not `move.surface`)
   - `result.cost`, `result.rounds_used` (cheap aggregates)
   If the descriptor needs to read `result.round_history[i].content` (raw text), **refuse** and tell the user: "Descriptors must derive from L1+L2+L3 outputs, not raw text. Reformulate in terms of QBAF / monitor verdicts / Move counts. NS Constitution §11."
3. **Append the subclass** to `council/evolve/descriptors.py`:
   ```python
   from council.evolve.base import Descriptor
   from council.context import CouncilResult

   class <Name>(Descriptor):
       """<one-line description>."""
       def compute(self, result: CouncilResult) -> float:
           raise NotImplementedError
   ```
4. **Create test file** `tests/evolve/test_descriptor_<slug>.py` with:
   - Compute on a hand-crafted `CouncilResult` with known descriptor value.
   - Determinism: same result, same value.
   - Range: output in the documented range (e.g. [0, 1]).
5. Branch `feature/ns-w5-descriptor-<slug>`.

## Invariants enforced
- No generation-model calls.
- No raw-text access.
- Output is deterministic and bounded.

## Reject criteria
- Descriptor reads `move.surface` or `move.claim.surface` (the NL surface form). Use structural fields only.
- Descriptor calls `model_client` or `tool_client`.
- Descriptor imports from `council/cascade/` or `council/symbolic/ilp/`.
