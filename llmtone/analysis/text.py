"""Tokenisation, segmentation and document-level metrics.

Deterministic by construction: the same input string always produces the same
numbers. No randomness, no model calls, no dependence on set or dict iteration
order in any value that reaches the profile.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

__all__ = [
    "normalise",
    "tokenise",
    "split_paragraphs",
    "split_sentences",
    "mtld",
    "BasicMetrics",
    "basic_metrics",
    "rate_per",
]

# A word is a run of letters/digits, optionally joined by apostrophes or hyphens.
# Curly apostrophes are normalised to straight ones before tokenising.
_WORD_RE = re.compile(r"[0-9A-Za-z]+(?:['\-][0-9A-Za-z]+)*")

# Sentence boundary: terminal punctuation, optional closing quote/bracket, space.
_SENT_BOUNDARY_RE = re.compile(r'(?<=[.!?])["\')\]]*\s+')

_PARAGRAPH_RE = re.compile(r"\n[ \t]*\n")

# A leading bullet or numbered-list marker.
BULLET_RE = re.compile(r"^\s*(?:[-*•‣◦]|\d+[.)])\s+")

# A markdown heading, or a short standalone line with no terminal punctuation.
HEADING_RE = re.compile(r"^\s*#{1,6}\s+\S")

# Tokens that end in "." without ending a sentence.
_ABBREVIATIONS = frozenset({
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g",
    "i.e", "approx", "dept", "fig", "no", "al", "inc", "ltd", "co", "corp",
    "cf", "viz", "min", "max", "est", "cca", "ca", "pp", "ed", "vol",
})

_TRAILING_TOKEN_RE = re.compile(r"([A-Za-z][A-Za-z.]*)\.[\"')\]]*\s*$")


def normalise(text: str) -> str:
    """Normalise unicode punctuation so downstream regexes see one form.

    Curly quotes become straight ones and non-breaking spaces become spaces.
    Dashes are left alone -- punctuation.py needs to tell them apart.
    """
    text = unicodedata.normalize("NFC", text)
    for src, dst in (
        ("’", "'"), ("‘", "'"),
        ("“", '"'), ("”", '"'),
        (" ", " "), ("﻿", ""),
    ):
        text = text.replace(src, dst)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def tokenise(text: str) -> list[str]:
    """Lowercased word tokens, in document order."""
    return [m.group(0).lower() for m in _WORD_RE.finditer(normalise(text))]


def split_paragraphs(text: str) -> list[str]:
    """Split on blank lines. Trailing/leading whitespace is stripped."""
    parts = _PARAGRAPH_RE.split(normalise(text).strip())
    return [p.strip() for p in parts if p.strip()]


def _split_list_items(paragraph: str) -> list[str]:
    """Treat a run of bullet/numbered lines as separate segments.

    List items rarely end in a full stop, so without this a five-item bullet
    list would be measured as one enormous sentence.
    """
    lines = paragraph.split("\n")
    if not any(BULLET_RE.match(line) for line in lines):
        return [paragraph]
    segments: list[str] = []
    current: list[str] = []
    for line in lines:
        if BULLET_RE.match(line) and current:
            segments.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        segments.append("\n".join(current))
    return [s.strip() for s in segments if s.strip()]


def _ends_with_abbreviation(chunk: str) -> bool:
    match = _TRAILING_TOKEN_RE.search(chunk)
    if not match:
        return False
    token = match.group(1).lower().rstrip(".")
    return token in _ABBREVIATIONS or len(token) == 1


def split_sentences(text: str) -> list[str]:
    """Split text into sentences.

    Paragraph and list-item boundaries always end a sentence, so unpunctuated
    headings and bullets are not glued to the text that follows them.
    """
    sentences: list[str] = []
    for paragraph in split_paragraphs(text):
        for segment in _split_list_items(paragraph):
            sentences.extend(_split_segment(segment))
    return sentences


def _split_segment(segment: str) -> list[str]:
    segment = segment.strip()
    if not segment:
        return []
    out: list[str] = []
    start = 0
    for match in _SENT_BOUNDARY_RE.finditer(segment):
        candidate = segment[start:match.start()]
        if _ends_with_abbreviation(candidate):
            continue
        if candidate.strip():
            out.append(candidate.strip())
        start = match.end()
    tail = segment[start:].strip()
    if tail:
        out.append(tail)
    return out


def mtld(tokens: list[str], threshold: float = 0.72) -> float:
    """Measure of Textual Lexical Diversity (McCarthy & Jarvis, 2010).

    Plain type-token ratio falls as a text gets longer, so it cannot compare a
    2000-word document with a 200-word email -- which is exactly what llmtone
    needs to do. MTLD measures the average number of words it takes for the
    running TTR to fall below ``threshold``, which is stable across lengths.

    Returns 0.0 for texts under 10 tokens, where the measure is meaningless.
    """
    if len(tokens) < 10:
        return 0.0
    forward = _mtld_pass(tokens, threshold)
    backward = _mtld_pass(list(reversed(tokens)), threshold)
    return round((forward + backward) / 2, 2)


def _mtld_pass(tokens: list[str], threshold: float) -> float:
    factors = 0.0
    types: set[str] = set()
    count = 0
    for token in tokens:
        count += 1
        types.add(token)
        if len(types) / count <= threshold:
            factors += 1
            types = set()
            count = 0
    if count > 0:
        remaining_ttr = len(types) / count
        factors += (1 - remaining_ttr) / (1 - threshold)
    if factors <= 0:
        return float(len(tokens))
    return len(tokens) / factors


def rate_per(count: int, total: int, per: int) -> float:
    """``count`` occurrences per ``per`` units of ``total``. 0.0 when empty."""
    if total <= 0:
        return 0.0
    return round(count * per / total, 4)


@dataclass(frozen=True)
class BasicMetrics:
    word_count: int
    sentence_count: int
    paragraph_count: int
    average_sentence_length: float
    sentence_length_variance: float
    average_paragraph_length: float
    average_word_length: float
    long_word_rate: float
    vocabulary_diversity: float
    unique_word_count: int
    heading_count: int
    bullet_count: int
    sentence_lengths: tuple[int, ...] = field(default=(), repr=False)

    def to_dict(self) -> dict:
        data = {
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "paragraph_count": self.paragraph_count,
            "average_sentence_length": self.average_sentence_length,
            "sentence_length_variance": self.sentence_length_variance,
            "average_paragraph_length": self.average_paragraph_length,
            "average_word_length": self.average_word_length,
            "long_word_rate": self.long_word_rate,
            "vocabulary_diversity": self.vocabulary_diversity,
            "unique_word_count": self.unique_word_count,
            "heading_count": self.heading_count,
            "bullet_count": self.bullet_count,
        }
        return data


def _population_variance(values: list[int]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def basic_metrics(text: str) -> BasicMetrics:
    text = normalise(text)
    tokens = tokenise(text)
    paragraphs = split_paragraphs(text)
    sentences = split_sentences(text)
    sentence_lengths = [len(tokenise(s)) for s in sentences]
    sentence_lengths = [n for n in sentence_lengths if n > 0]

    word_count = len(tokens)
    lines = [line for line in text.split("\n") if line.strip()]
    heading_count = sum(1 for line in lines if HEADING_RE.match(line))
    bullet_count = sum(1 for line in lines if BULLET_RE.match(line))

    long_words = sum(1 for t in tokens if len(t) >= 7)
    total_chars = sum(len(t) for t in tokens)

    return BasicMetrics(
        word_count=word_count,
        sentence_count=len(sentence_lengths),
        paragraph_count=len(paragraphs),
        average_sentence_length=(
            round(sum(sentence_lengths) / len(sentence_lengths), 2)
            if sentence_lengths else 0.0
        ),
        sentence_length_variance=round(_population_variance(sentence_lengths), 2),
        average_paragraph_length=(
            round(word_count / len(paragraphs), 2) if paragraphs else 0.0
        ),
        average_word_length=(
            round(total_chars / word_count, 2) if word_count else 0.0
        ),
        long_word_rate=rate_per(long_words, word_count, 100),
        vocabulary_diversity=mtld(tokens),
        unique_word_count=len(set(tokens)),
        heading_count=heading_count,
        bullet_count=bullet_count,
        sentence_lengths=tuple(sentence_lengths),
    )
