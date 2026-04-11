"""Tests for council/topology.py — communication graph abstractions.

Per testing.md requirements for Topology:
- get_adjacency_matrix(0) and get_adjacency_matrix(1)
- symmetry where expected
- communication_mode correctness
- StarTopology no-round-parity (architecture rule)
"""

from __future__ import annotations

import pytest

from council.context import CommunicationMode
from council.topology import (
    BusTopology,
    CompleteGraphTopology,
    DynamicStarTopology,
    RingTopology,
    StarTopology,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_symmetric(matrix: list[list[bool]]) -> bool:
    n = len(matrix)
    return all(matrix[i][j] == matrix[j][i] for i in range(n) for j in range(n))


def diagonal_false(matrix: list[list[bool]]) -> bool:
    return all(not matrix[i][i] for i in range(len(matrix)))


# ---------------------------------------------------------------------------
# Topology base contract
# ---------------------------------------------------------------------------


class TestTopologyBase:
    def test_requires_at_least_2_agents(self) -> None:
        with pytest.raises(ValueError):
            CompleteGraphTopology(1)

    def test_num_agents_stored(self) -> None:
        t = CompleteGraphTopology(4)
        assert t.num_agents == 4


# ---------------------------------------------------------------------------
# CompleteGraphTopology
# ---------------------------------------------------------------------------


class TestCompleteGraphTopology:
    def test_adjacency_round_0_all_off_diagonal_true(self) -> None:
        t = CompleteGraphTopology(3)
        m = t.get_adjacency_matrix(0)
        assert len(m) == 3
        assert diagonal_false(m)
        for i in range(3):
            for j in range(3):
                if i != j:
                    assert m[i][j] is True

    def test_adjacency_round_1_same_as_round_0(self) -> None:
        t = CompleteGraphTopology(3)
        assert t.get_adjacency_matrix(0) == t.get_adjacency_matrix(1)

    def test_adjacency_is_symmetric(self) -> None:
        t = CompleteGraphTopology(4)
        assert is_symmetric(t.get_adjacency_matrix(0))

    def test_communication_mode_is_individual(self) -> None:
        assert CompleteGraphTopology.communication_mode == CommunicationMode.INDIVIDUAL


# ---------------------------------------------------------------------------
# StarTopology — pure relay, no round parity
# ---------------------------------------------------------------------------


class TestStarTopology:
    def test_adjacency_round_0_equals_round_1(self) -> None:
        # Architecture rule: StarTopology must NOT alternate on round parity.
        t = StarTopology(4)
        assert t.get_adjacency_matrix(0) == t.get_adjacency_matrix(1)

    def test_adjacency_round_0_equals_round_5(self) -> None:
        t = StarTopology(4)
        assert t.get_adjacency_matrix(0) == t.get_adjacency_matrix(5)

    def test_adjacency_same_as_complete_graph(self) -> None:
        # StarTopology is a pure relay — all peripherals see all others (relayed).
        star = StarTopology(4)
        complete = CompleteGraphTopology(4)
        assert star.get_adjacency_matrix(0) == complete.get_adjacency_matrix(0)

    def test_adjacency_is_symmetric(self) -> None:
        t = StarTopology(5)
        assert is_symmetric(t.get_adjacency_matrix(0))

    def test_communication_mode_is_individual(self) -> None:
        assert StarTopology.communication_mode == CommunicationMode.INDIVIDUAL

    def test_no_privileged_agent(self) -> None:
        # No row should have a distinct pattern from any other — no "hub" with
        # different visibility than peripherals.
        t = StarTopology(4)
        m = t.get_adjacency_matrix(0)
        # All rows should be identical (complete graph adjacency).
        for i in range(4):
            for j in range(4):
                expected = i != j
                assert m[i][j] == expected


# ---------------------------------------------------------------------------
# DynamicStarTopology — alternating fan-out / fan-in (round-dependent)
# ---------------------------------------------------------------------------


class TestDynamicStarTopology:
    def test_even_round_hub_broadcasts_to_all_peripherals(self) -> None:
        # Even round (0, 2, ...): hub (index 0) sends to all peripherals.
        t = DynamicStarTopology(4)
        m = t.get_adjacency_matrix(0)
        # hub → peripherals: m[hub][peripheral] is True for peripheral != hub
        for j in range(1, 4):
            assert m[0][j] is True
        # peripherals don't see each other in fan-out
        for i in range(1, 4):
            for j in range(1, 4):
                assert m[i][j] is False

    def test_odd_round_peripherals_report_to_hub(self) -> None:
        # Odd round (1, 3, ...): all peripherals send to hub.
        t = DynamicStarTopology(4)
        m = t.get_adjacency_matrix(1)
        # peripherals → hub: m[peripheral][hub] is True
        for i in range(1, 4):
            assert m[i][0] is True
        # hub doesn't see other agents in fan-in (it receives only)
        for j in range(1, 4):
            assert m[0][j] is False

    def test_round_0_not_equal_to_round_1(self) -> None:
        t = DynamicStarTopology(4)
        assert t.get_adjacency_matrix(0) != t.get_adjacency_matrix(1)

    def test_round_2_same_as_round_0(self) -> None:
        t = DynamicStarTopology(4)
        assert t.get_adjacency_matrix(2) == t.get_adjacency_matrix(0)

    def test_even_round_not_symmetric(self) -> None:
        # Fan-out is directional: hub sends, peripherals receive only.
        t = DynamicStarTopology(4)
        assert not is_symmetric(t.get_adjacency_matrix(0))

    def test_communication_mode_is_relay(self) -> None:
        assert DynamicStarTopology.communication_mode == CommunicationMode.RELAY


# ---------------------------------------------------------------------------
# BusTopology
# ---------------------------------------------------------------------------


class TestBusTopology:
    def test_adjacency_complete_graph_shape(self) -> None:
        t = BusTopology(3)
        m = t.get_adjacency_matrix(0)
        assert diagonal_false(m)
        for i in range(3):
            for j in range(3):
                if i != j:
                    assert m[i][j] is True

    def test_adjacency_round_0_equals_round_1(self) -> None:
        t = BusTopology(3)
        assert t.get_adjacency_matrix(0) == t.get_adjacency_matrix(1)

    def test_adjacency_is_symmetric(self) -> None:
        assert is_symmetric(BusTopology(4).get_adjacency_matrix(0))

    def test_communication_mode_is_broadcast(self) -> None:
        assert BusTopology.communication_mode == CommunicationMode.BROADCAST


# ---------------------------------------------------------------------------
# RingTopology
# ---------------------------------------------------------------------------


class TestRingTopology:
    def test_each_agent_sees_only_predecessor(self) -> None:
        t = RingTopology(4)
        m = t.get_adjacency_matrix(0)
        for i in range(4):
            pred = (i - 1) % 4
            for j in range(4):
                if j == pred:
                    assert m[i][j] is True, f"agent {i} should see predecessor {pred}"
                else:
                    assert m[i][j] is False, f"agent {i} should not see agent {j}"

    def test_each_row_has_exactly_one_true(self) -> None:
        t = RingTopology(5)
        m = t.get_adjacency_matrix(0)
        for row in m:
            assert sum(row) == 1

    def test_not_symmetric(self) -> None:
        # Ring is directional (predecessor → agent), not symmetric.
        t = RingTopology(4)
        assert not is_symmetric(t.get_adjacency_matrix(0))

    def test_round_0_equals_round_1(self) -> None:
        t = RingTopology(4)
        assert t.get_adjacency_matrix(0) == t.get_adjacency_matrix(1)

    def test_communication_mode_is_relay(self) -> None:
        assert RingTopology.communication_mode == CommunicationMode.RELAY


# ---------------------------------------------------------------------------
# Cross-layer isolation
# ---------------------------------------------------------------------------


def test_topology_has_no_non_context_council_imports() -> None:
    import importlib.util

    spec = importlib.util.find_spec("council.topology")
    assert spec is not None and spec.origin is not None
    with open(spec.origin) as f:
        source = f.read()
    bad = [
        line
        for line in source.splitlines()
        if ("from council." in line or "import council." in line)
        and "council.context" not in line
        and not line.strip().startswith("#")
    ]
    assert bad == [], f"topology.py imports from non-context council modules: {bad}"
