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
    "Variation",
    "contradictions",
    "score_dimension",
    "score_all",
    "MIN_WORDS_FOR_CONSISTENCY",
    "SINGLE_SAMPLE_CONSISTENCY",
    "CONTEXT_SPREAD_POINTS",
    "CONTEXT_SCATTER_POINTS",
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

#: A dimension whose per-sample values span at least this many points is wide
#: enough to be worth saying out loud. 30 points is about the distance between
#: a work email and a message to a friend -- a single value in the middle
#: describes neither of them.
CONTEXT_SPREAD_POINTS = 30

#: ...but a range is set by its two most extreme samples, so a wide one can be
#: a single odd note. A dimension must also scatter this much (standard
#: deviation, in points) before it is called context-dependent. 15 points puts
#: consistency below SINGLE_SAMPLE_CONSISTENCY: the samples together are saying
#: less about one value than any one of them said alone.
CONTEXT_SCATTER_POINTS = 15.0


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


@dataclass(frozen=True)
class Variation:
    """One dimension the samples disagree about, and by how much."""

    name: str
    low: int
    high: int
    #: Standard deviation of the per-sample values. Says whether the range
    #: below is a real split or one unusual sample stretching it.
    scatter: float

    @property
    def spread(self) -> int:
        return self.high - self.low

    def to_dict(self) -> dict:
        return {
            "dimension": self.name,
            "low": self.low,
            "high": self.high,
            "scatter": self.scatter,
        }


def contradictions(
    results: dict[str, DimensionResult],
    threshold: int = CONTEXT_SPREAD_POINTS,
    scatter_threshold: float = CONTEXT_SCATTER_POINTS,
) -> list[Variation]:
    """Dimensions whose per-sample values both spread wide and scatter.

    A wide range does not mean the value is wrong. It means the person writes
    differently in different places, and one number is reporting the average of
    two habits rather than either of them -- which is register variation, the
    thing stylometry keeps rediscovering, not measurement error. Confidence has
    already been lowered for it through consistency; this names what happened.

    Both tests have to pass. Range alone is set by the two most extreme samples,
    so on a handful of short notes almost every dimension looks contradictory;
    requiring scatter as well means a range stretched by one mild outlier is not
    reported as a split. It does not rule out a lone *extreme* sample, and
    should not: one formal email among five casual notes is the signal, not
    noise. Samples too short to be usable for consistency never reach
    ``sample_values``, so a six-word reply counts for nothing either.

    Ordered widest range first -- the order the ranges are shown in -- then in
    :data:`DIMENSIONS` order, so the output is stable.
    """
    order = {d.name: index for index, d in enumerate(DIMENSIONS)}
    found = [
        Variation(
            name=name,
            low=min(result.sample_values),
            high=max(result.sample_values),
            scatter=round(_stdev(result.sample_values), 1),
        )
        for name, result in results.items()
        if len(result.sample_values) >= 2
    ]
    return sorted(
        (
            v for v in found
            if v.spread >= threshold and v.scatter >= scatter_threshold
        ),
        key=lambda v: (-v.spread, order.get(v.name, len(order))),
    )
