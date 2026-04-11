"""Preference extraction from LLM text — pure parsing, no model calls.

Constitution §3: ranking only parses text into preference structures.
No model calls, no prompt construction, no state mutation.
Constitution §4: json.loads primary; regex fallback only on JSONDecodeError.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PreferenceData:
    """Base preference record — always returned, even on parsing failure."""

    raw_text: str = ""


@dataclass(frozen=True, slots=True)
class RichPreference(PreferenceData):
    """Fully parsed preference with ordering, scores, and optional reasoning."""

    ordered_ids: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class Ranking(ABC):
    """Extract a preference from an agent's response text."""

    SCHEMA: ClassVar[dict[str, object]] = {}  # JSON schema injected into protocol prompts

    @abstractmethod
    def extract(self, text: str, agent_ids: list[str]) -> PreferenceData: ...

    def _regex_fallback(self, text: str, agent_ids: list[str]) -> PreferenceData:
        """Hook for subclasses — override for custom regex behaviour."""
        return PreferenceData(raw_text=text)


# ---------------------------------------------------------------------------
# StructuredRanking
# ---------------------------------------------------------------------------

_RANKING_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "ranking": {"type": "array", "items": {"type": "string"}},
        "scores": {"type": "object", "additionalProperties": {"type": "number"}},
        "reasoning": {"type": "string"},
    },
    "required": ["ranking", "scores"],
}


class StructuredRanking(Ranking):
    """JSON-primary preference extraction (Constitution §4).

    Expects: {"ranking": ["A", "B"], "scores": {"A": 9, "B": 5}, "reasoning": "..."}
    Falls back to _regex_fallback on JSONDecodeError.
    """

    SCHEMA = _RANKING_SCHEMA

    def extract(self, text: str, agent_ids: list[str]) -> PreferenceData:
        valid_ids = set(agent_ids)

        # --- Primary: JSON ---
        try:
            data = json.loads(text)
            ordered = [aid for aid in data.get("ranking", []) if aid in valid_ids]
            raw_scores: dict[str, object] = data.get("scores", {})
            scores: dict[str, float] = {}
            for k, v in raw_scores.items():
                if k in valid_ids and isinstance(v, (int, float)):
                    scores[k] = float(v)
            reasoning: str = data.get("reasoning", "")
            return RichPreference(
                raw_text=text,
                ordered_ids=ordered,
                scores=scores,
                reasoning=reasoning,
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.debug("StructuredRanking: JSON parse failed, using regex fallback")

        # --- Fallback ---
        return self._regex_fallback(text, agent_ids)

    def _regex_fallback(self, text: str, agent_ids: list[str]) -> PreferenceData:
        return RegexOrdinalRanking().extract(text, agent_ids)


# ---------------------------------------------------------------------------
# RegexOrdinalRanking
# ---------------------------------------------------------------------------

_RANKING_PATTERN = re.compile(
    r"(?:final\s+)?ranking\s*[:=]\s*([A-Za-z0-9_\-]+(?:\s*>\s*[A-Za-z0-9_\-]+)+)",
    re.IGNORECASE,
)


class RegexOrdinalRanking(Ranking):
    """Fallback ordinal parser for 'FINAL RANKING: A > B > C' patterns."""

    SCHEMA: ClassVar[dict[str, object]] = {}

    def extract(self, text: str, agent_ids: list[str]) -> PreferenceData:
        match = _RANKING_PATTERN.search(text)
        if not match:
            return PreferenceData(raw_text=text)

        parts = [p.strip() for p in match.group(1).split(">")]
        valid_ids = set(agent_ids)
        ordered = [p for p in parts if p in valid_ids]
        return RichPreference(raw_text=text, ordered_ids=ordered)


# ---------------------------------------------------------------------------
# NullRanking
# ---------------------------------------------------------------------------


class NullRanking(Ranking):
    """No-op ranking used when aggregation does not need preferences."""

    SCHEMA: ClassVar[dict[str, object]] = {}

    def extract(self, text: str, agent_ids: list[str]) -> PreferenceData:
        return PreferenceData(raw_text=text)
