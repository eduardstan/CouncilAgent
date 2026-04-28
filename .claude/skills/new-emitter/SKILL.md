---
name: new-emitter
description: Scaffolds a new QD Emitter subclass in council/evolve/emitters/<slug>.py plus tests. Use when the user says "add a new emitter" or "/new-emitter <Name>". Tests genome well-formedness on emitted children.
---

# new-emitter

Scaffold an `Emitter` (W5 / L5) for QD search.

## Inputs
- `<Name>` — PascalCase, ending in `Emitter`. Examples: `CMAESEmitter`, `LLMReflectiveEmitter`, `LLMDiffEmitter`, `StructuralEmitter`.

## Procedure

1. **Prerequisite check.** `council/evolve/{genome,archives}.py` must exist; the `Emitter` ABC must be defined. If not, stop.
2. **Append the subclass** to `council/evolve/emitters/<slug>.py`:
   ```python
   from council.evolve.base import Archive, Emitter
   from council.evolve.genome import CouncilGenome

   class <Name>(Emitter):
       """<one-line description>."""
       def emit(self, archive: Archive) -> list[CouncilGenome]:
           raise NotImplementedError
   ```
3. **Create test file** `tests/evolve/emitters/test_<slug>.py` with:
   - **Well-formedness:** every emitted genome round-trips to YAML and back.
   - **Validation:** every emitted genome passes `CouncilGenome.validate()`.
   - **Diversity:** emitted children are not all identical (entropy over a sample > 0).
   - **No-extras path:** if the emitter requires `pyribs` or LLM mutation, expose a pure-Python fallback that still produces valid genomes (Constitution §8).
4. Branch `feature/ns-w5-emitter-<slug>`.

## Invariants enforced
- Emitted genomes are always valid (YAML round-trip + `validate()`).
- Diversity is non-zero on a sample.
- Pure-Python fallback exists when extras are unavailable.

## Reject criteria
- Emitter generates malformed genomes.
- Emitter calls generation models in the no-extras path (Constitution §8).
