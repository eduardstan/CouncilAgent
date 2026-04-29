"""ToolClient — universal tool integration skeleton (W0 stub).

Real MCP / Z3 / clingo / Lean / Python-sandbox / web integrations are wired
in W1-W6. Core pipeline interacts only through this module (Constitution §8).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ToolRequest:
    tool: str
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolResponse:
    tool: str
    result: object
    cost_usd: float = 0.0


@dataclass(frozen=True, slots=True)
class ToolFailure:
    tool: str
    error: str


ToolResult = ToolResponse | ToolFailure


class ToolClient(ABC):
    @abstractmethod
    async def call(self, request: ToolRequest) -> ToolResult: ...


class StubToolClient(ToolClient):
    """No-op stub — used when no tools are configured (W0 default)."""

    async def call(self, request: ToolRequest) -> ToolResult:
        logger.debug("StubToolClient: tool=%s (no-op)", request.tool)
        return ToolFailure(tool=request.tool, error="no tool backend configured")
