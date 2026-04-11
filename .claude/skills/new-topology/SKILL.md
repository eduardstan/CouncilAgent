---
name: new-topology
description: Scaffolds a new Topology subclass in council/topology.py plus a matching test file. Use when the user says "add a new topology", "create a <name> topology", or "/new-topology <Name>". Enforces Constitution §3 — topology returns only an adjacency matrix and communication mode, NEVER hardcodes privileged agents or alternates behavior on round parity (unless named Dynamic*).
---

# new-topology

Scaffold a new communication `Topology` that conforms to the CouncilAgent architecture.

## Inputs
- `<Name>`: PascalCase name ending in `Topology`, e.g. `SmallWorldTopology`, `LayeredTopology`
- Optional: one-line description

## Procedure

1. **Prerequisite check.** `council/topology.py` and `council/context.py` must exist with `CommunicationMode`. If not, tell the user and stop.

2. **Read** `council/topology.py` for the base `Topology` class signature.

3. **Append the subclass**:
   ```python
   class <Name>(Topology):
       """<one-line description>."""

       communication_mode: ClassVar[CommunicationMode] = CommunicationMode.INDIVIDUAL

       def __init__(self, num_agents: int):
           if num_agents < 2:
               raise ValueError("<Name> requires num_agents >= 2")
           self.num_agents = num_agents

       def get_adjacency_matrix(self, round_index: int) -> list[list[bool]]:
           # Return an n x n boolean matrix. matrix[i][j] = True means
           # agent i's response is visible to agent j in this round.
           # Constitution §3: no privileged agents. No round-parity alternation
           # unless this class is explicitly named DynamicSomethingTopology.
           raise NotImplementedError("Fill in <Name>.get_adjacency_matrix")
   ```

4. **Refuse round-parity alternation** unless `<Name>` starts with `Dynamic`. If the user asks for round-dependent visibility on a non-Dynamic class, stop and say:
   > "Round-dependent visibility must live in a `Dynamic<Name>Topology` class per `.claude/rules/architecture.md`. Rename it or ask me to create `Dynamic<Name>Topology` instead."

5. **Create test file** `tests/council/test_topology_<snake_name>.py`:
   ```python
   import pytest
   from council.topology import <Name>
   from council.context import CommunicationMode

   def test_<snake_name>_adjacency_shape():
       t = <Name>(num_agents=4)
       m = t.get_adjacency_matrix(0)
       assert len(m) == 4
       assert all(len(row) == 4 for row in m)

   def test_<snake_name>_no_self_loops():
       t = <Name>(num_agents=4)
       m = t.get_adjacency_matrix(0)
       for i in range(4):
           assert m[i][i] is False, "an agent should not see its own response through the topology"

   def test_<snake_name>_has_communication_mode():
       t = <Name>(num_agents=3)
       assert t.communication_mode in CommunicationMode

   def test_<snake_name>_rejects_trivial_sizes():
       with pytest.raises(ValueError):
           <Name>(num_agents=1)

   # NOTE: if this class is Dynamic*, also test that adjacency differs across rounds.
   ```

6. **Branch**: `feature/p1-topology-<snake_name>`.

7. **Report**: files touched, invariants enforced, next step.

## Invariants enforced
- §3: no `agent_ids[0]` hardcoding, no alternation unless `Dynamic*`
- `communication_mode` class var is required
- No self-loops in adjacency
- `num_agents >= 2` validation
