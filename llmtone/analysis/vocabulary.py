"""Vocabulary features: what words this person reaches for, and what they avoid.

The "prefer" list is evidence of presence and is reasonably trustworthy. The
"avoid" list is evidence of *absence* -- a word from a curated candidate list
that never appears in the sample -- which is much weaker, and is only produced
once there is enough text for absence to mean anything (MIN_WORDS_FOR_AVOID).
See docs/scoring.md.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from . import lexicons as lex
from .text import normalise, rate_per, tokenise

__all__ = ["VocabularyMetrics", "vocabulary_metrics", "MIN_WORDS_FOR_AVOID"]

#: Below this many words, absence of a word is not evidence of anything.
MIN_WORDS_FOR_AVOID = 200

#: How many entries each surfaced list is capped at.
LIST_LIMIT = 12

_CAMEL_RE = re.compile(r"\b[a-z]+[A-Z][A-Za-z]*\b")
_SNAKE_RE = re.compile(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b")
_FILENAME_RE = re.compile(
    r"\b[\w.-]+\.(?:py|js|ts|tsx|json|ya?ml|md|sh|rs|go|java|rb|toml|cfg|"
    r"ini|sql|html|css|xml|csv|txt|lock)\b"
)
_ACRONYM_RE = re.compile(r"\b[A-Z]{2,6}s?\b")
_FLAG_RE = re.compile(r"(?<!\w)--[a-z][\w-]+")
_CODEISH_RE = re.compile(r"`[^`]+`|\b\w+\(\)")

# Curated avoid candidates, in priority order. Absence of one of these is the
# most informative kind of absence: they are common in AI-generated prose and
# corporate writing, so never using one is a real signal.
AVOID_CANDIDATES: tuple[str, ...] = (
    "furthermore", "moreover", "leverage", "utilize", "utilise",
    "delve", "robust", "seamless", "holistic", "synergy",
    "additionally", "thus", "hence", "endeavour", "endeavor",
    "facilitate", "commence", "ascertain", "stakeholder", "actionable",
    "streamline", "paradigm", "myriad", "plethora", "nonetheless",
    "notwithstanding", "aforementioned", "heretofore", "optimal",
    "impactful", "cutting-edge", "frictionless", "granular",
)

AVOID_PHRASE_CANDIDATES: tuple[str, ...] = (
    "it is important to note", "it should be noted", "in conclusion",
    "at the end of the day", "circle back", "touch base",
    "move the needle", "low hanging fruit", "in today's world",
)


def _count_phrases(text_lower: str, phrases) -> dict[str, int]:
    """Count phrase occurrences with word boundaries, longest first."""
    found: dict[str, int] = {}
    for phrase in phrases:
        pattern = r"\b" + re.escape(phrase).replace(r"\ ", r"\s+") + r"\b"
        n = len(re.findall(pattern, text_lower))
        if n:
            found[phrase] = n
    return found


#: Number words. Frequent in real writing, and never evidence of voice.
_NUMBER_WORDS = frozenset({
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "twenty", "thirty", "forty", "fifty",
    "hundred", "thousand", "million", "first", "second", "third",
})

#: Vague nouns and quantities that recur in any text regardless of style.
_NOT_DISTINCTIVE = frozenset({
    "someone", "something", "anyone", "anything", "everyone", "everything",
    "nobody", "nothing", "somebody", "week", "weeks", "month", "months",
    "year", "years", "hour", "hours", "minute", "minutes", "morning",
    "afternoon", "evening", "night", "today", "tomorrow", "yesterday",
    "part", "parts", "point", "points", "case", "cases", "number",
    "numbers", "end", "start", "side", "kind", "sort", "bit",
})


def _is_distinctive(word: str) -> bool:
    """Would seeing this word tell you anything about who wrote it?

    Contractions are excluded because ``contraction_preference`` already
    captures that habit far better than listing "it's" as favourite vocabulary.
    """
    if word in _NUMBER_WORDS or word in _NOT_DISTINCTIVE:
        return False
    if word in lex.CONTRACTIONS or "'" in word:
        return False
    if any(character.isdigit() for character in word):
        return False
    return True


def _top(counter: Counter, limit: int = LIST_LIMIT) -> list[str]:
    """Most frequent first, ties broken alphabetically so output is stable."""
    return [
        word for word, _ in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ][:limit]


@dataclass(frozen=True)
class VocabularyMetrics:
    word_count: int
    frequencies: Counter = field(repr=False)
    common_words: list[str]
    unusual_words: list[str]
    repeated_words: list[str]
    technical_terms: list[str]
    colloquialisms: list[str]
    filler_words: list[str]
    hedging_terms: list[str]
    buzzwords: list[str]
    formal_words: list[str]
    prefer: list[str]
    avoid: list[str]
    hedge_rate: float
    filler_rate: float
    buzzword_rate: float
    formal_vocab_rate: float
    colloquial_rate: float
    intensifier_rate: float
    humour_marker_rate: float
    technical_rate: float
    formal_transition_rate: float
    avoid_is_inferred_from_absence: bool

    def to_dict(self) -> dict:
        return {
            "common_words": self.common_words,
            "unusual_words": self.unusual_words,
            "repeated_words": self.repeated_words,
            "technical_terms": self.technical_terms,
            "colloquialisms": self.colloquialisms,
            "filler_words": self.filler_words,
            "hedging_terms": self.hedging_terms,
            "buzzwords": self.buzzwords,
            "formal_words": self.formal_words,
            "rates_per_100_words": {
                "buzzword": self.buzzword_rate,
                "colloquial": self.colloquial_rate,
                "filler": self.filler_rate,
                "formal_transition": self.formal_transition_rate,
                "formal_vocab": self.formal_vocab_rate,
                "hedge": self.hedge_rate,
                "humour_marker": self.humour_marker_rate,
                "intensifier": self.intensifier_rate,
                "technical": self.technical_rate,
            },
        }


def vocabulary_metrics(text: str) -> VocabularyMetrics:
    text = normalise(text)
    lower = text.lower()
    tokens = tokenise(text)
    words = len(tokens)
    freq = Counter(tokens)

    content = Counter({w: c for w, c in freq.items() if w not in lex.STOPWORDS
                       and len(w) > 2})

    hedge_words = Counter({w: c for w, c in freq.items() if w in lex.HEDGE_WORDS})
    hedge_phrases = _count_phrases(lower, lex.HEDGE_PHRASES)
    hedge_total = sum(hedge_words.values()) + sum(hedge_phrases.values())

    fillers = Counter({w: c for w, c in freq.items() if w in lex.FILLERS})
    buzzwords = Counter({w: c for w, c in freq.items() if w in lex.BUZZWORDS})
    buzz_phrases = _count_phrases(lower, lex.BUZZ_PHRASES)
    buzz_total = sum(buzzwords.values()) + sum(buzz_phrases.values())

    formal = Counter({w: c for w, c in freq.items() if w in lex.FORMAL_VOCAB})
    colloquial = Counter({w: c for w, c in freq.items() if w in lex.COLLOQUIALISMS})
    colloquial_phrases = _count_phrases(lower, lex.COLLOQUIAL_PHRASES)
    colloquial_total = sum(colloquial.values()) + sum(colloquial_phrases.values())

    intensifiers = sum(c for w, c in freq.items() if w in lex.INTENSIFIERS)
    humour = sum(c for w, c in freq.items() if w in lex.HUMOUR_MARKERS)
    humour += sum(lower.count(p) for p in lex.HUMOUR_PUNCTUATION)
    transitions = sum(c for w, c in freq.items() if w in lex.FORMAL_TRANSITIONS)

    # Technical vocabulary: lexicon hits plus shape-based detection.
    technical = Counter({w: c for w, c in freq.items() if w in lex.TECHNICAL_TERMS})
    pattern_hits: Counter = Counter()
    for pattern in (_CAMEL_RE, _SNAKE_RE, _FILENAME_RE, _FLAG_RE):
        for match in pattern.findall(text):
            pattern_hits[match.lower()] += 1
    for match in _ACRONYM_RE.findall(text):
        if match.lower() not in lex.STOPWORDS and match not in ("I", "A"):
            pattern_hits[match.lower()] += 1
    pattern_hits += Counter({m.lower(): 1 for m in _CODEISH_RE.findall(text)})
    technical_total = sum(technical.values()) + sum(pattern_hits.values())

    unusual = Counter({
        w: c for w, c in content.items()
        if len(w) >= 8 and c <= 2 and w not in lex.TECHNICAL_TERMS
    })
    repeated = Counter({w: c for w, c in content.items() if c >= 3})

    # --- prefer -------------------------------------------------------------
    # Style-bearing vocabulary only. An earlier version also included the most
    # repeated content words, which turned out to surface *topic* rather than
    # voice -- a profile built from work emails would tell a model to reach for
    # "archive" and "reporting", and the model would duly write about archives.
    # Domain vocabulary is reported separately as technical_terms, where a
    # consumer can treat it as subject matter rather than as style.
    style_words = Counter({
        w: c for w, c in freq.items()
        if _is_distinctive(w)
        and (
            w in lex.HEDGE_WORDS or w in lex.FILLERS
            or w in lex.COLLOQUIALISMS or w in lex.INTENSIFIERS
            or w in lex.HUMOUR_MARKERS
        )
    })
    style_phrases = Counter(hedge_phrases) + Counter(colloquial_phrases)

    prefer: list[str] = []
    for phrase, count in sorted(style_phrases.items(), key=lambda kv: (-kv[1], kv[0])):
        if count >= 2 and len(prefer) < 6:
            prefer.append(phrase)
    for word in _top(style_words, LIST_LIMIT):
        if style_words[word] >= 2 and word not in prefer and len(prefer) < LIST_LIMIT:
            prefer.append(word)

    # --- avoid (absence-based; see module docstring) ------------------------
    avoid: list[str] = []
    if words >= MIN_WORDS_FOR_AVOID:
        for candidate in AVOID_CANDIDATES:
            if freq.get(candidate, 0) == 0:
                plain = lex.FORMAL_TO_PLAIN.get(candidate)
                # Strongest evidence: they never use the formal word but do use
                # its plain equivalent. Otherwise it is a weaker default.
                if plain is None or freq.get(plain.split()[0], 0) > 0:
                    avoid.append(candidate)
            if len(avoid) >= 8:
                break
        for phrase in AVOID_PHRASE_CANDIDATES:
            if len(avoid) >= LIST_LIMIT:
                break
            if phrase not in lower:
                avoid.append(phrase)

    return VocabularyMetrics(
        word_count=words,
        frequencies=freq,
        common_words=_top(content),
        unusual_words=_top(unusual),
        repeated_words=_top(repeated),
        technical_terms=_top(technical + pattern_hits),
        colloquialisms=_top(colloquial + Counter(colloquial_phrases)),
        filler_words=_top(fillers),
        hedging_terms=_top(hedge_words + Counter(hedge_phrases)),
        buzzwords=_top(buzzwords + Counter(buzz_phrases)),
        formal_words=_top(formal),
        prefer=prefer[:LIST_LIMIT],
        avoid=avoid[:LIST_LIMIT],
        hedge_rate=rate_per(hedge_total, words, 100),
        filler_rate=rate_per(sum(fillers.values()), words, 100),
        buzzword_rate=rate_per(buzz_total, words, 100),
        formal_vocab_rate=rate_per(sum(formal.values()), words, 100),
        colloquial_rate=rate_per(colloquial_total, words, 100),
        intensifier_rate=rate_per(intensifiers, words, 100),
        humour_marker_rate=rate_per(humour, words, 100),
        technical_rate=rate_per(technical_total, words, 100),
        formal_transition_rate=rate_per(transitions, words, 100),
        avoid_is_inferred_from_absence=True,
    )
