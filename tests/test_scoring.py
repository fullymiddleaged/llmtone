"""Scoring and confidence.

The dimension tests are deliberately relative -- "the formal fixture scores
higher on formality than the casual one" -- rather than golden numbers. The
weights in dimensions.py are meant to be retuned; a test suite that pins exact
values would punish exactly the change the design invites.
"""

from __future__ import annotations

import pytest

from llmtone.analysis import analyse
from llmtone.scoring import DIMENSIONS, DIMENSIONS_BY_NAME, linear_map, score_all
from llmtone.scoring.scorer import (
    CONSISTENCY_FLOOR,
    SINGLE_SAMPLE_CONSISTENCY,
    score_dimension,
)


@pytest.fixture(scope="module")
def scored(request) -> dict[str, dict[str, int]]:
    from conftest import STYLES, read_fixture

    out = {}
    for style in STYLES:
        features = analyse(read_fixture(style)).features
        out[style] = {
            d.name: int(round(d.score(features))) for d in DIMENSIONS
        }
    return out


class TestWeights:
    def test_every_dimension_sums_to_one(self):
        for dimension in DIMENSIONS:
            total = sum(abs(w) for w in dimension.weights.values())
            assert total == pytest.approx(1.0)

    def test_scores_stay_in_range_for_extreme_input(self):
        absurd = {name: 10_000.0 for name in DIMENSIONS[0].weights}
        for dimension in DIMENSIONS:
            features = {f: 10_000.0 for f in dimension.weights}
            assert 0.0 <= dimension.score(features) <= 100.0
            assert 0.0 <= dimension.score({f: -10_000.0 for f in features}) <= 100.0
        assert absurd  # the fixture above is only meaningful if non-empty


class TestLinearMap:
    def test_clamps_at_both_ends(self):
        assert linear_map(-5, 0, 10) == 0.0
        assert linear_map(50, 0, 10) == 100.0

    def test_midpoint(self):
        assert linear_map(5, 0, 10) == 50.0

    def test_degenerate_range_does_not_explode(self):
        assert linear_map(5, 10, 10) == 0.0


class TestDiscrimination:
    """The four fixtures must land where a human would put them."""

    def test_formality(self, scored):
        assert scored["formal_professional"]["formality"] > scored["casual_direct"]["formality"]
        assert scored["verbose_technical"]["formality"] > scored["warm_conversational"]["formality"]

    def test_directness(self, scored):
        assert scored["casual_direct"]["directness"] > scored["verbose_technical"]["directness"]

    def test_warmth(self, scored):
        warm = scored["warm_conversational"]["warmth"]
        assert warm > scored["formal_professional"]["warmth"]
        assert warm > scored["verbose_technical"]["warmth"]

    def test_conciseness(self, scored):
        assert scored["casual_direct"]["conciseness"] > scored["verbose_technical"]["conciseness"]

    def test_technicality(self, scored):
        assert scored["verbose_technical"]["technicality"] > scored["warm_conversational"]["technicality"]

    def test_conversationality(self, scored):
        assert scored["casual_direct"]["conversationality"] > scored["formal_professional"]["conversationality"]

    def test_hedging(self, scored):
        assert scored["verbose_technical"]["hedging"] > scored["casual_direct"]["hedging"]


class TestConfidence:
    def _features(self, text):
        analysis = analyse(text)
        return analysis.features, analysis.word_count

    def test_confidence_never_exceeds_the_ceiling(self, fixtures):
        text = "\n\n".join(fixtures.values()) * 5
        features, words = self._features(text)
        results = score_all(features, words, [(features, words)] * 4)
        for name, result in results.items():
            assert result.confidence <= DIMENSIONS_BY_NAME[name].confidence_ceiling

    def test_confidence_rises_with_more_words(self, fixtures):
        short = fixtures["casual_direct"][:400]
        long = fixtures["casual_direct"]
        dimension = DIMENSIONS_BY_NAME["formality"]

        short_features, short_words = self._features(short)
        long_features, long_words = self._features(long)
        assert (
            score_dimension(dimension, long_features, long_words).confidence
            >= score_dimension(dimension, short_features, short_words).confidence
        )

    def test_zero_words_gives_zero_confidence(self):
        results = score_all({}, 0, [])
        assert all(r.confidence == 0.0 for r in results.values())

    def test_a_single_sample_is_penalised(self, fixtures):
        features, words = self._features(fixtures["casual_direct"])
        result = score_dimension(
            DIMENSIONS_BY_NAME["conciseness"], features, words, [(features, words)]
        )
        assert result.consistency == SINGLE_SAMPLE_CONSISTENCY

    def test_consistent_samples_beat_conflicting_ones(self, fixtures):
        casual, casual_words = self._features(fixtures["casual_direct"])
        formal, formal_words = self._features(fixtures["formal_professional"])
        dimension = DIMENSIONS_BY_NAME["formality"]

        agreeing = score_dimension(
            dimension, casual, casual_words * 2,
            [(casual, casual_words), (casual, casual_words)],
        )
        conflicting = score_dimension(
            dimension, casual, casual_words * 2,
            [(casual, casual_words), (formal, formal_words)],
        )
        assert conflicting.confidence < agreeing.confidence

    def test_consistency_has_a_floor(self, fixtures):
        """Contradictory evidence lowers confidence; it does not erase it."""
        casual, cw = self._features(fixtures["casual_direct"])
        formal, fw = self._features(fixtures["formal_professional"])
        result = score_dimension(
            DIMENSIONS_BY_NAME["formality"], casual, cw + fw,
            [(casual, cw), (formal, fw), (casual, cw), (formal, fw)],
        )
        assert result.consistency >= CONSISTENCY_FLOOR
        assert result.confidence > 0

    def test_tiny_samples_are_ignored_for_consistency(self, fixtures):
        """A six-word note should not be evidence of inconsistency."""
        big, big_words = self._features(fixtures["casual_direct"])
        tiny, tiny_words = self._features("Sure. Sounds good to me.")
        result = score_dimension(
            DIMENSIONS_BY_NAME["formality"], big, big_words,
            [(big, big_words), (tiny, tiny_words)],
        )
        assert result.consistency == SINGLE_SAMPLE_CONSISTENCY


class TestExplainability:
    def test_contributions_sum_to_the_value(self, fixtures):
        features = analyse(fixtures["casual_direct"]).features
        for dimension in DIMENSIONS:
            total = sum(dimension.contributions(features).values())
            assert total == pytest.approx(dimension.score(features), abs=0.01)

    def test_explain_exposes_the_three_confidence_factors(self, fixtures):
        features = analyse(fixtures["casual_direct"]).features
        explained = score_dimension(
            DIMENSIONS_BY_NAME["formality"], features, 500
        ).explain()
        assert set(explained["confidence_factors"]) == {
            "ceiling", "coverage", "consistency"
        }
