"""Deterministic text analysis.

``analyse(text)`` returns an :class:`Analysis`: the raw observable metrics plus a
flat ``features`` mapping. ``features`` is the only thing the scoring layer is
allowed to read, which keeps the boundary between "what we measured" and "what
we concluded" a real one (see docs/scoring.md).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from . import lexicons
from .punctuation import PunctuationMetrics, punctuation_metrics
from .syntax import APPROXIMATE_METRICS, SyntaxMetrics, syntax_metrics
from .text import BasicMetrics, basic_metrics, normalise, split_sentences, tokenise
from .vocabulary import VocabularyMetrics, vocabulary_metrics

__all__ = [
    "Analysis",
    "analyse",
    "FEATURE_NAMES",
    "APPROXIMATE_METRICS",
    "lexicons",
    "basic_metrics",
    "syntax_metrics",
    "punctuation_metrics",
    "vocabulary_metrics",
]

#: Every feature the scoring layer may consume. Adding a feature here without
#: adding a range in scoring/dimensions.py is caught by that module's checks.
FEATURE_NAMES: tuple[str, ...] = (
    "avg_sentence_length",
    "sentence_length_variance",
    "avg_paragraph_length",
    "avg_word_length",
    "long_word_rate",
    "vocabulary_diversity",
    "contraction_rate",
    "first_person_rate",
    "second_person_rate",
    "passive_rate",
    "question_rate",
    "fragment_rate",
    "conjunction_rate",
    "subordinate_rate",
    "initial_conjunction_rate",
    "imperative_rate",
    "hedge_rate",
    "filler_rate",
    "buzzword_rate",
    "formal_vocab_rate",
    "colloquial_rate",
    "intensifier_rate",
    "humour_marker_rate",
    "technical_rate",
    "formal_transition_rate",
    "exclamation_rate",
    "comma_rate",
    "semicolon_rate",
    "parenthesis_rate",
    "em_dash_rate",
)

_PHRASE_MIN_COUNT = 2
_PHRASE_LIMIT = 10

# A recurring phrase is only interesting if it carries voice. Phrases that open
# with one of these, or contain a hedge, are the ones worth showing a model.
_PHRASE_SEEDS = frozenset(
    lexicons.FIRST_PERSON | {"let", "worth", "probably", "honestly", "look"}
)


def _recurring_phrases(tokens: list[str]) -> list[str]:
    """Repeated 2-4 word phrases that carry voice, most frequent first."""
    counts: Counter = Counter()
    for size in (4, 3, 2):
        for i in range(len(tokens) - size + 1):
            gram = tokens[i:i + size]
            if gram[0] not in _PHRASE_SEEDS:
                continue
            if not any(
                t in lexicons.HEDGE_WORDS or t in _PHRASE_SEEDS for t in gram
            ):
                continue
            counts[" ".join(gram)] += 1

    chosen: list[str] = []
    for phrase, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if count < _PHRASE_MIN_COUNT:
            continue
        # Skip a phrase already covered by a longer one we kept.
        if any(phrase in kept for kept in chosen):
            continue
        chosen.append(phrase)
        if len(chosen) >= _PHRASE_LIMIT:
            break
    return chosen


@dataclass(frozen=True)
class Analysis:
    text_length: int
    basic: BasicMetrics
    syntax: SyntaxMetrics
    punctuation: PunctuationMetrics
    vocabulary: VocabularyMetrics
    features: dict[str, float]
    phrases: list[str]

    @property
    def word_count(self) -> int:
        return self.basic.word_count

    def to_dict(self) -> dict:
        """Full metric dump.

        Carries no prose: no sentences, no phrasing beyond the recurring
        fragments in ``recurring_phrases``. It does carry individual words --
        that is what ``common_words`` and ``unusual_words`` are for -- so it is
        derived from your writing, not free of it. See docs/privacy.md.
        """
        return {
            "basic": self.basic.to_dict(),
            "syntax": self.syntax.to_dict(),
            "punctuation": self.punctuation.to_dict(),
            "vocabulary": self.vocabulary.to_dict(),
            "features": dict(sorted(self.features.items())),
            "recurring_phrases": self.phrases,
            "approximate_metrics": list(APPROXIMATE_METRICS),
        }


def analyse(text: str) -> Analysis:
    """Analyse a block of text. Pure function: no I/O, no state, no network."""
    text = normalise(text)
    basic = basic_metrics(text)
    syn = syntax_metrics(text)
    punct = punctuation_metrics(text)
    vocab = vocabulary_metrics(text)
    sentences = max(basic.sentence_count, 1)

    features: dict[str, float] = {
        "avg_sentence_length": basic.average_sentence_length,
        "sentence_length_variance": basic.sentence_length_variance,
        "avg_paragraph_length": basic.average_paragraph_length,
        "avg_word_length": basic.average_word_length,
        "long_word_rate": basic.long_word_rate,
        "vocabulary_diversity": basic.vocabulary_diversity,
        "contraction_rate": syn.contraction_rate,
        "first_person_rate": syn.first_person_rate,
        "second_person_rate": syn.second_person_rate,
        "passive_rate": syn.passive_rate,
        "question_rate": syn.question_rate,
        "fragment_rate": syn.fragment_rate,
        "conjunction_rate": syn.conjunction_rate,
        "subordinate_rate": syn.subordinate_rate,
        "initial_conjunction_rate": syn.initial_conjunction_rate,
        "imperative_rate": syn.imperative_rate,
        "hedge_rate": vocab.hedge_rate,
        "filler_rate": vocab.filler_rate,
        "buzzword_rate": vocab.buzzword_rate,
        "formal_vocab_rate": vocab.formal_vocab_rate,
        "colloquial_rate": vocab.colloquial_rate,
        "intensifier_rate": vocab.intensifier_rate,
        "humour_marker_rate": vocab.humour_marker_rate,
        "technical_rate": vocab.technical_rate,
        "formal_transition_rate": vocab.formal_transition_rate,
        "exclamation_rate": round(
            punct.counts["exclamation"] * 100 / sentences, 4
        ),
        "comma_rate": round(punct.rates["comma"] / 10, 4),
        "semicolon_rate": punct.rates["semicolon"],
        "parenthesis_rate": punct.rates["parentheses"],
        "em_dash_rate": punct.rates["em_dash"],
    }

    missing = set(FEATURE_NAMES) - set(features)
    if missing:  # pragma: no cover - guards against an incomplete edit
        raise AssertionError(f"features missing from analyse(): {sorted(missing)}")

    return Analysis(
        text_length=len(text),
        basic=basic,
        syntax=syn,
        punctuation=punct,
        vocabulary=vocab,
        features=features,
        phrases=_recurring_phrases(tokenise(text)),
    )
