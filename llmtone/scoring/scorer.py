"""Turn observed features into dimension values and confidences.

Values come from the corpus as a whole. Confidence comes from three separate
factors, each of which answers a different question:

  ceiling      Can this dimension be inferred reliably at all by counting words?
  coverage     Is there enough writing to have seen it?
  consistency  Does the person do the same thing across samples?

  confidence = ceiling x coverage x consistency

Nothing here is learned, fitted or sampled. Given the same texts, this module
returns the same numbers on every machine, forever.
"""

from __future__ import annotations

from dataclasses import dataclass

from .dimensions import DIMENSIONS, Dimension

__all__ = [
    "DimensionResult",
    "score_dimension",
    "score_all",
    "MIN_WORDS_FOR_CONSISTENCY",
    "SINGLE_SAMPLE_CONSISTENCY",
]

#: Samples shorter than this are too noisy to say anything about consistency.
#: They still contribute to the corpus value and to coverage.
MIN_WORDS_FOR_CONSISTENCY = 40

#: With one sample there is nothing to be consistent *with*, so confidence takes
#: a fixed haircut rather than pretending to perfect agreement.
SINGLE_SAMPLE_CONSISTENCY = 0.70

#: A dimension varying by this many points across samples drives consistency to
#: its floor. 50 points is half the scale -- genuinely contradictory evidence.
CONSISTENCY_SPREAD_SCALE = 50.0

#: Consistency never falls below this; conflicting evidence lowers confidence,
#: it does not erase the observation.
CONSISTENCY_FLOOR = 0.30


@dataclass(frozen=True)
class DimensionResult:
    name: str
    value: int
    confidence: float
    coverage: float
    consistency: float
    ceiling: float
    contributions: dict[str, float]
    sample_values: list[int]

    def to_dict(self) -> dict:
        return {"value": self.value, "confidence": self.confidence}

    def explain(self) -> dict:
        """Everything behind the number, for debugging and `--explain`."""
        return {
            "value": self.value,
            "confidence": self.confidence,
            "confidence_factors": {
                "ceiling": self.ceiling,
                "coverage": self.coverage,
                "consistency": self.consistency,
            },
            "contributions": dict(sorted(self.contributions.items())),
            "per_sample_values": self.sample_values,
        }


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return variance ** 0.5


def score_dimension(
    dimension: Dimension,
    corpus_features: dict[str, float],
    total_words: int,
    sample_features: list[tuple[dict[str, float], int]] | None = None,
) -> DimensionResult:
    """Score one dimension.

    ``sample_features`` is a list of ``(features, word_count)`` per sample, used
    only to measure consistency. The value itself always comes from
    ``corpus_features``, which is the analysis of every sample concatenated --
    so a 2000-word document naturally outweighs a 20-word note without any
    weighting arithmetic.
    """
    contributions = dimension.contributions(corpus_features)
    value = sum(contributions.values())

    coverage = min(1.0, total_words / dimension.target_words) if total_words else 0.0

    usable = [
        feats for feats, words in (sample_features or [])
        if words >= MIN_WORDS_FOR_CONSISTENCY
    ]
    sample_values = [dimension.score(feats) for feats in usable]
    if len(sample_values) < 2:
        consistency = SINGLE_SAMPLE_CONSISTENCY
    else:
        spread = _stdev(sample_values) / CONSISTENCY_SPREAD_SCALE
        consistency = max(CONSISTENCY_FLOOR, 1.0 - spread)

    confidence = dimension.confidence_ceiling * coverage * consistency

    return DimensionResult(
        name=dimension.name,
        value=int(round(max(0.0, min(100.0, value)))),
        confidence=round(min(dimension.confidence_ceiling, confidence), 2),
        coverage=round(coverage, 3),
        consistency=round(consistency, 3),
        ceiling=dimension.confidence_ceiling,
        contributions=contributions,
        sample_values=[int(round(v)) for v in sample_values],
    )


def score_all(
    corpus_features: dict[str, float],
    total_words: int,
    sample_features: list[tuple[dict[str, float], int]] | None = None,
) -> dict[str, DimensionResult]:
    """Score every dimension. Keys are in :data:`DIMENSIONS` order."""
    return {
        d.name: score_dimension(d, corpus_features, total_words, sample_features)
        for d in DIMENSIONS
    }
