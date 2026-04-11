"""Answer normalization — turn raw LLM output into a canonical comparison key.

Constitution §4: structured output (json.loads) is the primary path.
Regex is a fallback only, used exclusively on JSONDecodeError.

No model calls here. Normalizers are pure async functions over strings.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Regex patterns tried in order when JSON parsing fails.
# Each pattern must have a single capture group for the answer value.
_FALLBACK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\banswer\s*[:=]\s*([^\n,\.]+)", re.IGNORECASE),
    re.compile(r"\bthe answer is\s+([^\n,\.]+)", re.IGNORECASE),
    re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*$"),  # bare numeric
]


class AnswerNormalizer(ABC):
    """Convert a raw LLM response string to a canonical, comparable form."""

    @abstractmethod
    async def normalize(self, response: str) -> str: ...


class StructuredOutputNormalizer(AnswerNormalizer):
    """Extracts the answer from a JSON response, falls back to regex, then strip+lower.

    Primary path: json.loads() → read answer_field → str(value).strip().lower()
    Fallback (JSONDecodeError only): _FALLBACK_PATTERNS → first match → strip().lower()
    Final fallback: response.strip().lower()

    Constitution §4: regex is NEVER tried on valid JSON.
    """

    def __init__(self, answer_field: str = "answer") -> None:
        self._answer_field = answer_field

    async def normalize(self, response: str) -> str:
        # --- Primary: JSON ---
        try:
            data = json.loads(response)
            if isinstance(data, dict) and self._answer_field in data:
                return str(data[self._answer_field]).strip().lower()
            # Valid JSON but answer_field missing — fall through to regex.
            logger.debug(
                "StructuredOutputNormalizer: JSON parsed but field %r missing; "
                "falling back to strip+lower",
                self._answer_field,
            )
            return response.strip().lower()
        except json.JSONDecodeError:
            pass  # expected — try regex

        # --- Fallback: regex patterns ---
        for pattern in _FALLBACK_PATTERNS:
            match = pattern.search(response)
            if match:
                return match.group(1).strip().lower()

        # --- Final fallback: strip + lower ---
        return response.strip().lower()


class IdentityNormalizer(AnswerNormalizer):
    """No extraction — returns the response stripped and lowercased.

    Use for free-text tasks where the raw content is already the canonical form.
    """

    async def normalize(self, response: str) -> str:
        return response.strip().lower()
