---
name: new-property
description: Scaffolds a new LTL_f Property subclass in council/symbolic/verify/properties.py plus tests. Use when the user says "add a new property" or "/new-property <Name> <formula>". Enforces the property has both ⊤ and ⊥ test traces.
---

# new-property

Scaffold a named LTL₍f₎ `Property` (W1 / L1) for the verifier library.

## Inputs
- `<Name>` — PascalCase, e.g. `NoSycophancyCascade`, `RefutationReachable`.
- `<formula>` — LTL₍f₎ source, e.g. `G (challenge_accepted -> O proposal_accepted)`.
- Optional one-line natural-language reading.

## Procedure

1. **Prerequisite check.** `council/symbolic/verify/{ltlf,monitor,properties}.py` must exist; `council/dialect/trace.py` must expose `Trace.to_events()`. If not, stop.
2. **AP availability.** Identify the atomic propositions used in `<formula>`. Each must appear as a key in some event emitted by `Trace.to_events()`. If a needed AP is missing, **stop** and say: "Add AP `X` to `dialect/trace.py:to_events()` first; this property cannot compile without it."
3. **Append the subclass** to `council/symbolic/verify/properties.py`:
   ```python
   class <Name>(Property):
       """<one-line natural-language description>."""
       name: ClassVar[str] = "<Name>"
       formula: ClassVar[str] = "<formula>"
       def compile(self) -> LTL3Monitor:
           return ltl3_compile(self.formula)
   ```
4. **Append two tests** to `tests/symbolic/verify/test_properties.py`:
   - `test_<snake_name>_positive` — a trace that satisfies the property; final verdict ⊤.
   - `test_<snake_name>_negative` — a trace that violates it; some verdict ⊥.
5. Run `uv run pytest tests/symbolic/verify/test_properties.py -k <snake_name>`.
6. Branch `feature/ns-w1-property-<slug>`.

## Invariants enforced
- Both ⊤ and ⊥ tests required (no half-tested properties).
- All APs must exist before the property compiles.
- The property is added to the named-property registry in `properties.py`.

## Reject criteria
- Formula references undefined APs.
- Only one of the two tests written.
- The property is non-monotorable (verify by attempting `ltl3_compile`; if it raises, refuse).
