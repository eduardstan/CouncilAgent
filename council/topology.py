"""Topology hierarchy — controls agent visibility during deliberation.

CommunicationMode: BROADCAST (all-to-all), INDIVIDUAL (hub-spoke), RELAY (chain).
Topologies return adjacency matrices; core.py uses these to build VisibilityContext.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

import numpy as np


class CommunicationMode(StrEnum):
    BROADCAST = "broadcast"
    INDIVIDUAL = "individual"
    RELAY = "relay"


class Topology(ABC):
    def __init__(self, n_agents: int) -> None:
        self.n_agents = n_agents

    @abstractmethod
    def get_adjacency_matrix(self, round_index: int) -> np.ndarray: ...

    @property
    @abstractmethod
    def communication_mode(self) -> CommunicationMode: ...


class CompleteGraphTopology(Topology):
    """All agents can see all others — BROADCAST."""

    @property
    def communication_mode(self) -> CommunicationMode:
        return CommunicationMode.BROADCAST

    def get_adjacency_matrix(self, round_index: int) -> np.ndarray:
        m = np.ones((self.n_agents, self.n_agents), dtype=int)
        np.fill_diagonal(m, 0)
        return m


class StarTopology(Topology):
    """Agent 0 is hub; spokes communicate only through hub — INDIVIDUAL."""

    @property
    def communication_mode(self) -> CommunicationMode:
        return CommunicationMode.INDIVIDUAL

    def get_adjacency_matrix(self, round_index: int) -> np.ndarray:
        m = np.zeros((self.n_agents, self.n_agents), dtype=int)
        for j in range(1, self.n_agents):
            m[0, j] = 1
            m[j, 0] = 1
        return m


class RingTopology(Topology):
    """Each agent sees only left/right neighbours — RELAY."""

    @property
    def communication_mode(self) -> CommunicationMode:
        return CommunicationMode.RELAY

    def get_adjacency_matrix(self, round_index: int) -> np.ndarray:
        n = self.n_agents
        m = np.zeros((n, n), dtype=int)
        for i in range(n):
            m[i, (i + 1) % n] = 1
            m[i, (i - 1) % n] = 1
        return m


class BusTopology(Topology):
    """Sequential relay without wrap-around — RELAY."""

    @property
    def communication_mode(self) -> CommunicationMode:
        return CommunicationMode.RELAY

    def get_adjacency_matrix(self, round_index: int) -> np.ndarray:
        n = self.n_agents
        m = np.zeros((n, n), dtype=int)
        for i in range(n - 1):
            m[i, i + 1] = 1
        return m
