"""Tests for council/normalizer.py — answer normalization.

Per testing.md: table-driven (raw_input, expected_canonical) pairs covering
JSON-wrapped, plain-text, numerical, and malformed inputs.

Regression Issue 3: all three of ["The answer is 72.", "72", "answer: 72"]
must normalize to the same canonical string.
"""

from __future__ import annotations

import pytest

from council.normalizer import IdentityNormalizer, StructuredOutputNormalizer

# ---------------------------------------------------------------------------
# StructuredOutputNormalizer — table-driven
# ---------------------------------------------------------------------------

STRUCTURED_CASES: list[tuple[str, str]] = [
    # JSON primary path
    ('{"answer": 72, "reasoning": "7x8 is 56, 8x9 is 72"}', "72"),
    ('{"answer": "Paris", "confidence": 0.9}', "paris"),
    ('{"answer": "  Hello World  "}', "hello world"),
    ('{"answer": true}', "true"),
    # Custom field
    ('{"result": 42}', "42"),  # with answer_field="result"
    # Regex fallback path
    ("The answer is 72.", "72"),
    ("answer: 72", "72"),
    ("72", "72"),
    # Whitespace / case normalisation
    ("  PARIS  ", "paris"),
    # Malformed JSON → strip + lower fallback
    ('malformed {', "malformed {"),
    ('{"broken": }', '{"broken": }'),
]


@pytest.mark.parametrize("raw,expected", STRUCTURED_CASES[:4] + STRUCTURED_CASES[5:])
async def test_structured_normalizer_table(raw: str, expected: str) -> None:
    norm = StructuredOutputNormalizer()
    result = await norm.normalize(raw)
    assert result == expected, f"raw={raw!r} → got {result!r}, want {expected!r}"


async def test_structured_normalizer_custom_answer_field() -> None:
    norm = StructuredOutputNormalizer(answer_field="result")
    result = await norm.normalize('{"result": 42}')
    assert result == "42"


# ---------------------------------------------------------------------------
# Regression Issue 3 — the three surface forms of "72" must all normalise to "72"
# ---------------------------------------------------------------------------


async def test_issue3_regression_all_forms_normalize_to_same() -> None:
    """Issue 3: MajorityVote must see a single canonical key for all three forms."""
    norm = StructuredOutputNormalizer()
    forms = ["The answer is 72.", "72", "answer: 72"]
    canonical = [await norm.normalize(f) for f in forms]
    assert len(set(canonical)) == 1, f"Expected all same, got {canonical}"
    assert canonical[0] == "72"


# ---------------------------------------------------------------------------
# JSON primary path is tried before regex
# ---------------------------------------------------------------------------


async def test_json_path_used_for_valid_json() -> None:
    """Valid JSON must never hit the regex path — verified by using an answer
    that regex would NOT extract (no numeric or 'answer:' pattern)."""
    norm = StructuredOutputNormalizer()
    raw = '{"answer": "blue whale"}'
    result = await norm.normalize(raw)
    assert result == "blue whale"


async def test_regex_fallback_used_only_on_json_decode_error() -> None:
    """Regex fallback should not interfere when JSON parses successfully."""
    norm = StructuredOutputNormalizer()
    # This has a valid JSON parse but no 'answer' field — fallback is strip+lower.
    raw = '{"reasoning": "some thought"}'
    result = await norm.normalize(raw)
    # Falls through to strip+lower of the raw string.
    assert result == raw.strip().lower()


# ---------------------------------------------------------------------------
# IdentityNormalizer
# ---------------------------------------------------------------------------


IDENTITY_CASES: list[tuple[str, str]] = [
    ("Hello World", "hello world"),
    ("  spaces  ", "spaces"),
    ("72", "72"),
    ("", ""),
    ("MiXeD CaSe", "mixed case"),
]


@pytest.mark.parametrize("raw,expected", IDENTITY_CASES)
async def test_identity_normalizer_table(raw: str, expected: str) -> None:
    norm = IdentityNormalizer()
    result = await norm.normalize(raw)
    assert result == expected


# ---------------------------------------------------------------------------
# Cross-layer isolation
# ---------------------------------------------------------------------------


def test_normalizer_has_no_non_context_council_imports() -> None:
    import importlib.util

    spec = importlib.util.find_spec("council.normalizer")
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
    assert bad == [], f"normalizer.py imports from non-context council modules: {bad}"
