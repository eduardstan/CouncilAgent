"""Tests for council/ranking.py — preference extraction from LLM text.

Per testing.md:
- StructuredRanking: JSON primary success + malformed fallback (Issue 4 regression)
- RegexOrdinalRanking: parses "FINAL RANKING: A > B > C"
- NullRanking: always returns empty PreferenceData
- JSON path never reaches regex on valid input
"""

from __future__ import annotations

from council.ranking import (
    NullRanking,
    PreferenceData,
    RegexOrdinalRanking,
    RichPreference,
    StructuredRanking,
)

# ---------------------------------------------------------------------------
# StructuredRanking — Issue 4 regression
# ---------------------------------------------------------------------------


class TestStructuredRanking:
    def test_issue4_regression_valid_json_returns_rich_preference(self) -> None:
        """Regression Issue 4: StructuredRanking.extract succeeds on valid JSON."""
        ranking = StructuredRanking()
        result = ranking.extract(
            '{"ranking": ["A", "B"], "scores": {"A": 9, "B": 5}}',
            agent_ids=["A", "B"],
        )
        assert isinstance(result, RichPreference)
        assert result.ordered_ids == ["A", "B"]
        assert result.scores == {"A": 9.0, "B": 5.0}

    def test_malformed_json_does_not_raise(self) -> None:
        """Regression Issue 4: malformed JSON falls back gracefully."""
        ranking = StructuredRanking()
        result = ranking.extract("this is not json at all", agent_ids=["A", "B"])
        assert isinstance(result, PreferenceData)  # may be RichPreference or base

    def test_reasoning_extracted_when_present(self) -> None:
        ranking = StructuredRanking()
        result = ranking.extract(
            '{"ranking": ["A", "B"], "scores": {"A": 8, "B": 6}, "reasoning": "A was clearer"}',
            agent_ids=["A", "B"],
        )
        assert isinstance(result, RichPreference)
        assert result.reasoning == "A was clearer"

    def test_unknown_agent_ids_excluded_from_scores(self) -> None:
        ranking = StructuredRanking()
        result = ranking.extract(
            '{"ranking": ["A", "B", "X"], "scores": {"A": 9, "B": 5, "X": 7}}',
            agent_ids=["A", "B"],  # X is not a valid agent
        )
        assert isinstance(result, RichPreference)
        assert "X" not in result.scores

    def test_scores_converted_to_float(self) -> None:
        ranking = StructuredRanking()
        result = ranking.extract(
            '{"ranking": ["A"], "scores": {"A": 9}}',
            agent_ids=["A"],
        )
        assert isinstance(result, RichPreference)
        assert isinstance(result.scores["A"], float)

    def test_empty_agent_ids_gives_empty_scores(self) -> None:
        ranking = StructuredRanking()
        result = ranking.extract(
            '{"ranking": [], "scores": {}}',
            agent_ids=[],
        )
        assert isinstance(result, RichPreference)
        assert result.ordered_ids == []
        assert result.scores == {}

    def test_schema_is_class_level_dict(self) -> None:
        assert isinstance(StructuredRanking.SCHEMA, dict)
        assert "properties" in StructuredRanking.SCHEMA

    def test_json_path_does_not_invoke_regex_on_valid_json(self) -> None:
        """Valid JSON must not hit the regex fallback — inject a spy via subclassing."""
        regex_called = []

        class SpyRanking(StructuredRanking):
            def _regex_fallback(self, text: str, agent_ids: list[str]) -> PreferenceData:
                regex_called.append(text)
                return super()._regex_fallback(text, agent_ids)

        spy = SpyRanking()
        spy.extract('{"ranking": ["A"], "scores": {"A": 7}}', agent_ids=["A"])
        assert regex_called == [], "regex fallback should not be called on valid JSON"

    def test_markdown_json_fence_stripped_before_parse(self) -> None:
        """Audit §7 regression: LLM wrapping JSON in ```json ... ``` fences must still parse."""
        ranking = StructuredRanking()
        fenced = '```json\n{"ranking": ["A", "B"], "scores": {"A": 9, "B": 5}}\n```'
        result = ranking.extract(fenced, agent_ids=["A", "B"])
        assert isinstance(result, RichPreference)
        assert result.ordered_ids == ["A", "B"]


# ---------------------------------------------------------------------------
# RegexOrdinalRanking
# ---------------------------------------------------------------------------


class TestRegexOrdinalRanking:
    def test_parses_greater_than_chain(self) -> None:
        ranking = RegexOrdinalRanking()
        result = ranking.extract("FINAL RANKING: A > B > C", agent_ids=["A", "B", "C"])
        assert isinstance(result, RichPreference)
        assert result.ordered_ids == ["A", "B", "C"]

    def test_case_insensitive_keyword(self) -> None:
        ranking = RegexOrdinalRanking()
        result = ranking.extract("final ranking: B > A", agent_ids=["A", "B"])
        assert isinstance(result, RichPreference)
        assert result.ordered_ids[0] == "B"

    def test_no_match_returns_empty_preference(self) -> None:
        ranking = RegexOrdinalRanking()
        result = ranking.extract("I can't decide.", agent_ids=["A", "B"])
        assert isinstance(result, PreferenceData)
        # Should not raise regardless of content.

    def test_schema_is_empty(self) -> None:
        assert RegexOrdinalRanking.SCHEMA == {}


# ---------------------------------------------------------------------------
# NullRanking
# ---------------------------------------------------------------------------


class TestNullRanking:
    def test_always_returns_preference_data(self) -> None:
        ranking = NullRanking()
        result = ranking.extract("anything", agent_ids=["A", "B"])
        assert isinstance(result, PreferenceData)

    def test_schema_is_empty(self) -> None:
        assert NullRanking.SCHEMA == {}


# ---------------------------------------------------------------------------
# Cross-layer isolation
# ---------------------------------------------------------------------------


def test_ranking_has_no_non_context_council_imports() -> None:
    import importlib.util

    spec = importlib.util.find_spec("council.ranking")
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
    assert bad == [], f"ranking.py imports from non-context council modules: {bad}"
