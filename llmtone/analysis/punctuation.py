"""Punctuation counts, rates and frequency bands.

Rates are per 1000 words. Bands are per-mark, because base rates differ by more
than an order of magnitude: 20 commas per 1000 words is unremarkable, 20
semicolons per 1000 words is a personality. The thresholds live in
:data:`BAND_THRESHOLDS` and are rough general-English base rates -- they are a
starting point to tune, not a finding.
"""

from __future__ import annotations

from dataclasses import dataclass

from .text import normalise, rate_per, tokenise

__all__ = ["PunctuationMetrics", "punctuation_metrics", "BAND_THRESHOLDS", "band"]

#: mark -> literal(s) counted for it. Order matters: em/en dashes are counted
#: before hyphens so a "--" is not also counted as two hyphens.
MARKS: dict[str, tuple[str, ...]] = {
    "comma": (",",),
    "period": (".",),
    "semicolon": (";",),
    "colon": (":",),
    "parentheses": ("(",),
    "em_dash": ("—", "--"),
    "en_dash": ("–",),
    "hyphen": ("-",),
    "exclamation": ("!",),
    "question": ("?",),
    "ellipsis": ("…", "..."),
    "quote": ('"',),
}

#: mark -> (max rate to still be "rare", max rate to still be "occasional").
#: Anything above the second value is "frequent"; a count of exactly 0 is
#: always "never". Rates are per 1000 words.
BAND_THRESHOLDS: dict[str, tuple[float, float]] = {
    "comma": (20.0, 55.0),
    "period": (30.0, 70.0),
    "semicolon": (0.8, 3.0),
    "colon": (1.5, 6.0),
    "parentheses": (2.0, 8.0),
    "em_dash": (1.0, 5.0),
    "en_dash": (0.5, 2.0),
    "hyphen": (3.0, 12.0),
    "exclamation": (0.5, 3.0),
    "question": (2.0, 8.0),
    "ellipsis": (0.5, 2.0),
    "quote": (2.0, 10.0),
}

BANDS = ("never", "rare", "occasional", "frequent")


def band(mark: str, rate: float, count: int) -> str:
    """Bucket a per-1000-word rate into never/rare/occasional/frequent."""
    if count == 0:
        return "never"
    rare_max, occasional_max = BAND_THRESHOLDS.get(mark, (1.0, 5.0))
    if rate <= rare_max:
        return "rare"
    if rate <= occasional_max:
        return "occasional"
    return "frequent"


@dataclass(frozen=True)
class PunctuationMetrics:
    counts: dict[str, int]
    rates: dict[str, float]
    bands: dict[str, str]
    word_count: int

    def to_dict(self) -> dict:
        return {
            "counts": dict(sorted(self.counts.items())),
            "rates_per_1000_words": dict(sorted(self.rates.items())),
            "bands": dict(sorted(self.bands.items())),
        }


def punctuation_metrics(text: str) -> PunctuationMetrics:
    text = normalise(text)
    words = len(tokenise(text))

    working = text
    counts: dict[str, int] = {}
    # Multi-character marks are removed from the working copy as they are
    # counted, so "--" is not double-counted as two hyphens and "..." is not
    # counted as three periods.
    for mark in ("ellipsis", "em_dash", "en_dash"):
        total = 0
        for literal in MARKS[mark]:
            total += working.count(literal)
            working = working.replace(literal, "\x00")
        counts[mark] = total

    for mark, literals in MARKS.items():
        if mark in counts:
            continue
        counts[mark] = sum(working.count(literal) for literal in literals)

    rates = {m: rate_per(c, words, 1000) for m, c in counts.items()}
    bands = {m: band(m, rates[m], counts[m]) for m in counts}
    return PunctuationMetrics(
        counts=counts, rates=rates, bands=bands, word_count=words
    )
