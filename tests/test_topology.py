"""Tests for council/topology.py — topology hierarchy per testing.md rules."""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# CommunicationMode
# ---------------------------------------------------------------------------

def test_communication_mode_values() -> None:
    from council.topology import CommunicationMode
    assert CommunicationMode.BROADCAST.value == "broadcast"
    assert CommunicationMode.INDIVIDUAL.value == "individual"
    assert CommunicationMode.RELAY.value == "relay"


# ---------------------------------------------------------------------------
# CompleteGraphTopology — all pairs can communicate
# ---------------------------------------------------------------------------

def test_complete_graph_adjacency_round0() -> None:
    from council.topology import CompleteGraphTopology
    t = CompleteGraphTopology(n_agents=3)
    m = t.get_adjacency_matrix(0)
    assert m.shape == (3, 3)
    # Complete: every pair is connected (diagonal=0)
    for i in range(3):
        for j in range(3):
            if i != j:
                assert m[i, j] == 1


def test_complete_graph_adjacency_round1() -> None:
    from council.topology import CompleteGraphTopology
    t = CompleteGraphTopology(n_agents=3)
    m0 = t.get_adjacency_matrix(0)
    m1 = t.get_adjacency_matrix(1)
    assert np.array_equal(m0, m1), "CompleteGraph adjacency is round-invariant"


def test_complete_graph_is_symmetric() -> None:
    from council.topology import CompleteGraphTopology
    t = CompleteGraphTopology(n_agents=4)
    m = t.get_adjacency_matrix(0)
    assert np.array_equal(m, m.T)


def test_complete_graph_communication_mode() -> None:
    from council.topology import CommunicationMode, CompleteGraphTopology
    t = CompleteGraphTopology(n_agents=3)
    assert t.communication_mode == CommunicationMode.BROADCAST


# ---------------------------------------------------------------------------
# StarTopology — hub + spokes
# ---------------------------------------------------------------------------

def test_star_topology_adjacency_round0() -> None:
    from council.topology import StarTopology
    t = StarTopology(n_agents=4)  # agent 0 is hub
    m = t.get_adjacency_matrix(0)
    # Hub (0) connects to all spokes
    for j in range(1, 4):
        assert m[0, j] == 1
        assert m[j, 0] == 1
    # Spokes do not connect to each other
    for i in range(1, 4):
        for j in range(1, 4):
            if i != j:
                assert m[i, j] == 0


def test_star_topology_communication_mode() -> None:
    from council.topology import CommunicationMode, StarTopology
    t = StarTopology(n_agents=3)
    assert t.communication_mode == CommunicationMode.INDIVIDUAL


# ---------------------------------------------------------------------------
# RingTopology — each agent sees only neighbours
# ---------------------------------------------------------------------------

def test_ring_topology_adjacency_round0() -> None:
    from council.topology import RingTopology
    t = RingTopology(n_agents=4)
    m = t.get_adjacency_matrix(0)
    # Each agent connects to neighbours ±1 (wrap)
    assert m[0, 1] == 1
    assert m[0, 3] == 1
    assert m[0, 2] == 0


def test_ring_topology_is_symmetric() -> None:
    from council.topology import RingTopology
    t = RingTopology(n_agents=5)
    m = t.get_adjacency_matrix(0)
    assert np.array_equal(m, m.T)


def test_ring_topology_communication_mode() -> None:
    from council.topology import CommunicationMode, RingTopology
    t = RingTopology(n_agents=4)
    assert t.communication_mode == CommunicationMode.RELAY


# ---------------------------------------------------------------------------
# BusTopology — sequential relay
# ---------------------------------------------------------------------------

def test_bus_topology_adjacency_round0() -> None:
    from council.topology import BusTopology
    t = BusTopology(n_agents=4)
    m = t.get_adjacency_matrix(0)
    # Each agent sees only the next one in line
    assert m[0, 1] == 1
    assert m[1, 2] == 1
    assert m[2, 3] == 1
    assert m[3, 0] == 0  # no wrap in bus


def test_bus_topology_communication_mode() -> None:
    from council.topology import BusTopology, CommunicationMode
    t = BusTopology(n_agents=3)
    assert t.communication_mode == CommunicationMode.RELAY
