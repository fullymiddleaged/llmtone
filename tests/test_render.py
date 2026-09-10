"""Rendering: the prose summary and the model-independent instructions.

The rule under test throughout: a low-confidence dimension is never stated as
a fact.
"""

from __future__ import annotations

from llmtone.profile import (
    CONFIDENCE_THRESHOLD,
    DimensionScore,
    build_profile,
    describe_dimension,
    render_instructions,
    render_summary,
)

FIXED = {
    "profile_id": "test0000",
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
}


def make(texts):
    return build_profile(texts, **FIXED)


class TestDescribeDimension:
    def test_bands_are_ordered(self):
        assert describe_dimension("formality", 5) == "very casual"
        assert describe_dimension("formality", 95) == "formal"

    def test_unknown_dimension_degrades_gracefully(self):
        assert "42" in describe_dimension("not_a_dimension", 42)


class TestSummary:
    def test_mentions_established_dimensions(self, fixtures):
        profile = make([fixtures["casual_direct"]] * 3)
        summary = render_summary(profile)
        assert summary.startswith("You're ")

    def test_low_confidence_dimensions_are_not_stated_as_fact(self, fixtures):
        profile = make([fixtures["casual_direct"]])
        for name, score in profile.style.items():
            profile.style[name] = DimensionScore(score.value, 0.1)
        summary = render_summary(profile)
        assert "Not yet confident about" in summary
        assert not summary.startswith("You're ")

    def test_lists_prefer_and_avoid(self, fixtures):
        profile = make([fixtures["casual_direct"]] * 3)
        summary = render_summary(profile)
        assert "Prefer" in summary
        assert "treat as a hint" in summary  # the honesty caveat on avoid

    def test_empty_profile_says_so_plainly(self):
        assert "isn't enough writing yet" in render_summary(make([]))


class TestInstructions:
    def test_describes_behaviour_not_personality(self, fixtures):
        text = render_instructions(make([fixtures["casual_direct"]] * 3))
        assert "writing habits, not personality traits" in text
        assert "Do not imitate or copy any source text literally." in text

    def test_omits_low_confidence_dimensions_entirely(self, fixtures):
        profile = make([fixtures["warm_conversational"]] * 3)
        confident = [
            name for name, score in profile.style.items()
            if score.confidence >= CONFIDENCE_THRESHOLD
        ]
        unconfident = [
            name for name, score in profile.style.items()
            if score.confidence < CONFIDENCE_THRESHOLD
        ]
        text = render_instructions(profile)
        for name in unconfident:
            phrase = describe_dimension(name, profile.style[name].value)
            assert phrase.capitalize() not in text
        assert confident  # the test is vacuous unless something is confident

    def test_different_writers_get_different_instructions(self, fixtures):
        casual = render_instructions(make([fixtures["casual_direct"]] * 3))
        formal = render_instructions(make([fixtures["formal_professional"]] * 3))
        assert casual != formal
        assert "Use contractions naturally." in casual
        assert "Avoid contractions." in formal

    def test_mentions_punctuation_the_writer_never_uses(self, fixtures):
        text = render_instructions(make([fixtures["casual_direct"]] * 3))
        assert "Do not use:" in text

    def test_empty_profile_produces_safe_instructions(self):
        text = render_instructions(make([]))
        assert "Not enough is known" in text
        assert "Do not imitate" in text

    def test_output_is_plain_text_a_model_can_take_verbatim(self, fixtures):
        text = render_instructions(make([fixtures["verbose_technical"]] * 2))
        assert text.strip()
        assert "{" not in text and "}" not in text
