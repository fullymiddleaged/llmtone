"""Style dimensions: the weights, ranges and confidence parameters.

This module is data, not logic. Every judgement the scorer makes is a number in
this file, and you can change any of them without touching a line of code in
scorer.py. That is the point: llmtone would rather be a set of rules you can
argue with than a model you cannot inspect.

Reading a Dimension
-------------------
``weights`` maps a feature name to a signed weight. A positive weight means
"more of this feature means more of this dimension"; a negative weight means the
inverse. The absolute values sum to 1.0, so a dimension always lands in 0-100.

``target_words`` is how much writing is needed before the value is considered
fully covered. ``confidence_ceiling`` is the highest confidence this dimension
can ever reach -- an honest admission that some things cannot be inferred
reliably by counting words. Humour has the lowest ceiling for that reason.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "Dimension",
    "DIMENSIONS",
    "DIMENSION_NAMES",
    "FEATURE_RANGES",
    "linear_map",
]

#: feature -> (low, high). A feature at or below ``low`` maps to 0, at or above
#: ``high`` maps to 100, and interpolates linearly in between. Ranges are
#: plausible bounds for ordinary English prose, not hard limits. They are
#: deliberately narrow: a range much wider than real writing ever reaches
#: squashes that feature towards 0 and lets sentence length quietly dominate
#: every dimension. Retune these against your own corpus if yours differs.
FEATURE_RANGES: dict[str, tuple[float, float]] = {
    "avg_sentence_length": (8.0, 30.0),
    "sentence_length_variance": (10.0, 120.0),
    "avg_paragraph_length": (20.0, 120.0),
    "avg_word_length": (3.6, 6.2),
    "long_word_rate": (8.0, 35.0),
    "vocabulary_diversity": (30.0, 110.0),
    "contraction_rate": (0.0, 6.0),
    "first_person_rate": (0.0, 8.0),
    "second_person_rate": (0.0, 4.0),
    "passive_rate": (0.0, 40.0),
    "question_rate": (0.0, 25.0),
    "fragment_rate": (0.0, 25.0),
    "conjunction_rate": (0.0, 8.0),
    "subordinate_rate": (0.0, 80.0),
    "initial_conjunction_rate": (0.0, 20.0),
    "imperative_rate": (0.0, 25.0),
    "hedge_rate": (0.0, 2.5),
    "filler_rate": (0.0, 2.5),
    "buzzword_rate": (0.0, 1.5),
    "formal_vocab_rate": (0.0, 2.5),
    "colloquial_rate": (0.0, 2.0),
    "intensifier_rate": (0.0, 1.5),
    "humour_marker_rate": (0.0, 1.5),
    "technical_rate": (0.0, 4.0),
    "formal_transition_rate": (0.0, 1.2),
    "exclamation_rate": (0.0, 20.0),
    "comma_rate": (2.0, 12.0),
    "semicolon_rate": (0.0, 6.0),
    "parenthesis_rate": (0.0, 15.0),
    "em_dash_rate": (0.0, 15.0),
}


def linear_map(value: float, low: float, high: float) -> float:
    """Map ``value`` from the range [low, high] onto 0-100, clamped."""
    if high <= low:
        return 0.0
    scaled = (value - low) / (high - low) * 100.0
    return max(0.0, min(100.0, scaled))


@dataclass(frozen=True)
class Dimension:
    name: str
    description: str
    weights: dict[str, float]
    target_words: int
    confidence_ceiling: float
    low_label: str
    high_label: str

    def contributions(self, features: dict[str, float]) -> dict[str, float]:
        """Per-feature contribution to this dimension's 0-100 value.

        Exposed so ``llmtone analyse --explain`` and the tests can show exactly
        why a score came out where it did.
        """
        out: dict[str, float] = {}
        for feature, weight in self.weights.items():
            low, high = FEATURE_RANGES[feature]
            mapped = linear_map(features.get(feature, 0.0), low, high)
            if weight < 0:
                mapped = 100.0 - mapped
            out[feature] = round(abs(weight) * mapped, 4)
        return out

    def score(self, features: dict[str, float]) -> float:
        return round(sum(self.contributions(features).values()), 4)


DIMENSIONS: tuple[Dimension, ...] = (
    Dimension(
        name="formality",
        description="How formal the register is.",
        weights={
            "contraction_rate": -0.22,
            "formal_vocab_rate": 0.20,
            "colloquial_rate": -0.18,
            "avg_sentence_length": 0.12,
            "formal_transition_rate": 0.10,
            "long_word_rate": 0.10,
            "first_person_rate": -0.08,
        },
        target_words=350,
        confidence_ceiling=0.90,
        low_label="casual",
        high_label="formal",
    ),
    Dimension(
        name="directness",
        description="How much is said outright versus softened.",
        weights={
            "hedge_rate": -0.28,
            "imperative_rate": 0.18,
            "filler_rate": -0.12,
            "passive_rate": -0.12,
            "avg_sentence_length": -0.12,
            "initial_conjunction_rate": 0.10,
            "second_person_rate": 0.08,
        },
        target_words=450,
        confidence_ceiling=0.85,
        low_label="indirect",
        high_label="direct",
    ),
    Dimension(
        name="warmth",
        description="How personal and reader-facing the writing is.",
        weights={
            "second_person_rate": 0.22,
            "exclamation_rate": 0.14,
            "colloquial_rate": 0.14,
            "formal_vocab_rate": -0.14,
            "first_person_rate": 0.12,
            "question_rate": 0.12,
            "intensifier_rate": 0.12,
        },
        target_words=500,
        confidence_ceiling=0.72,
        low_label="detached",
        high_label="warm",
    ),
    Dimension(
        name="conciseness",
        description="How much is said in how few words.",
        weights={
            "avg_sentence_length": -0.30,
            "avg_paragraph_length": -0.20,
            "filler_rate": -0.16,
            "hedge_rate": -0.12,
            "subordinate_rate": -0.12,
            "fragment_rate": 0.10,
        },
        target_words=300,
        confidence_ceiling=0.90,
        low_label="expansive",
        high_label="concise",
    ),
    Dimension(
        name="humour",
        description="Playfulness in the writing. The least reliable dimension.",
        weights={
            "humour_marker_rate": 0.40,
            "colloquial_rate": 0.20,
            "exclamation_rate": 0.12,
            "parenthesis_rate": 0.12,
            "intensifier_rate": 0.08,
            "formal_vocab_rate": -0.08,
        },
        target_words=900,
        confidence_ceiling=0.55,
        low_label="straight-faced",
        high_label="playful",
    ),
    Dimension(
        name="hedging",
        description="How often claims are qualified.",
        weights={
            "hedge_rate": 0.45,
            "filler_rate": 0.15,
            "passive_rate": 0.15,
            "imperative_rate": -0.15,
            "subordinate_rate": 0.10,
        },
        target_words=400,
        confidence_ceiling=0.85,
        low_label="unqualified",
        high_label="hedged",
    ),
    Dimension(
        name="technicality",
        description="How much domain vocabulary the writing assumes.",
        weights={
            "technical_rate": 0.45,
            "vocabulary_diversity": 0.15,
            "long_word_rate": 0.12,
            "colloquial_rate": -0.10,
            "avg_word_length": 0.10,
            "passive_rate": 0.08,
        },
        target_words=350,
        confidence_ceiling=0.88,
        low_label="plain",
        high_label="technical",
    ),
    Dimension(
        name="conversationality",
        description="How much it reads like speech rather than a document.",
        weights={
            "contraction_rate": 0.25,
            "second_person_rate": 0.15,
            "colloquial_rate": 0.15,
            "formal_vocab_rate": -0.15,
            "question_rate": 0.10,
            "initial_conjunction_rate": 0.10,
            "fragment_rate": 0.10,
        },
        target_words=350,
        confidence_ceiling=0.88,
        low_label="written",
        high_label="spoken",
    ),
)

DIMENSION_NAMES: tuple[str, ...] = tuple(d.name for d in DIMENSIONS)

DIMENSIONS_BY_NAME: dict[str, Dimension] = {d.name: d for d in DIMENSIONS}


def _validate() -> None:
    """Fail at import time rather than producing a quietly wrong profile."""
    for dimension in DIMENSIONS:
        total = sum(abs(w) for w in dimension.weights.values())
        if abs(total - 1.0) > 1e-9:
            raise AssertionError(
                f"{dimension.name}: weights must sum to 1.0, got {total:.4f}"
            )
        unknown = set(dimension.weights) - set(FEATURE_RANGES)
        if unknown:
            raise AssertionError(
                f"{dimension.name}: no range defined for {sorted(unknown)}"
            )
        if not 0.0 < dimension.confidence_ceiling <= 1.0:
            raise AssertionError(f"{dimension.name}: bad confidence ceiling")


_validate()
