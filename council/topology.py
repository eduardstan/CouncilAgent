"""Communication graph abstractions — pure topology, no prompts, no model calls.

Each Topology subclass answers one question: given a round index, which agents
can see which other agents? The answer is an adjacency matrix. Nothing more.

Constitution §3: topology controls visibility only. No privileged agents,
no prompt construction, no model calls. No 'chairman' label anywhere.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from council.context import CommunicationMode


class Topology(ABC):
    """Base class for all communication topologies."""

    communication_mode: CommunicationMode  # class-level attribute, set by subclass

    def __init__(self, num_agents: int) -> None:
        if num_agents < 2:
            raise ValueError(f"num_agents must be >= 2, got {num_agents}")
        self.num_agents = num_agents

    @abstractmethod
    def get_adjacency_matrix(self, round_index: int) -> list[list[bool]]:
        """Return an n-by-n boolean matrix where matrix[i][j] is True iff agent i
        can see agent j's previous output in this round."""
        ...


class CompleteGraphTopology(Topology):
    """Every agent sees every other agent. Static; ignores round_index."""

    communication_mode = CommunicationMode.INDIVIDUAL

    def get_adjacency_matrix(self, round_index: int) -> list[list[bool]]:
        n = self.num_agents
        return [[i != j for j in range(n)] for i in range(n)]


class StarTopology(Topology):
    """Pure relay — same adjacency as CompleteGraph, but RELAY communication mode.

    The hub is infrastructure only (not an agent). All peripherals see all
    other peripherals via the 2-hop hub relay. Adjacency is static across all
    rounds (architecture rule: no round-parity alternation — that lives in
    DynamicStarTopology).

    The RELAY mode is semantically distinct from CompleteGraphTopology's
    INDIVIDUAL mode: protocols receive the same visibility but know that
    messages are routed rather than sent peer-to-peer.
    """

    communication_mode = CommunicationMode.RELAY

    def get_adjacency_matrix(self, round_index: int) -> list[list[bool]]:
        # Pure relay: everyone sees everyone (2-hop via hub, same result as complete).
        n = self.num_agents
        return [[i != j for j in range(n)] for i in range(n)]


class DynamicStarTopology(Topology):
    """Alternating fan-out / fan-in visibility (round-dependent).

    Index 0 is the hub (infrastructure routing node — not a privileged agent).
    - Even rounds (0, 2, …): hub broadcasts to all peripherals (fan-out).
      matrix[0][j] = True for j > 0; all other entries False.
    - Odd rounds (1, 3, …): all peripherals report to hub (fan-in).
      matrix[i][0] = True for i > 0; all other entries False.
    """

    communication_mode = CommunicationMode.RELAY

    def get_adjacency_matrix(self, round_index: int) -> list[list[bool]]:
        n = self.num_agents
        m = [[False] * n for _ in range(n)]
        if round_index % 2 == 0:
            # Fan-out: hub (0) → peripherals
            for j in range(1, n):
                m[0][j] = True
        else:
            # Fan-in: peripherals → hub (0)
            for i in range(1, n):
                m[i][0] = True
        return m


class BusTopology(Topology):
    """Complete-graph visibility with broadcast communication mode.

    Identical adjacency to CompleteGraphTopology, but semantically different:
    messages are shared on a common board rather than sent individually.
    """

    communication_mode = CommunicationMode.BROADCAST

    def get_adjacency_matrix(self, round_index: int) -> list[list[bool]]:
        n = self.num_agents
        return [[i != j for j in range(n)] for i in range(n)]


class RingTopology(Topology):
    """Each agent sees only its immediate predecessor (circular).

    agent i sees agent (i-1) % n. Directional — not symmetric.
    Static across rounds.
    """

    communication_mode = CommunicationMode.RELAY

    def get_adjacency_matrix(self, round_index: int) -> list[list[bool]]:
        n = self.num_agents
        m = [[False] * n for _ in range(n)]
        for i in range(n):
            m[i][(i - 1) % n] = True
        return m
