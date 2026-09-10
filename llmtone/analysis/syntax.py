"""Sentence-level syntactic features.

Three of these metrics are approximations of things that properly need a parser:
passive voice, sentence fragments and subordinate clauses. Each is returned with
``approximate: True`` so nothing downstream can mistake it for a measurement.
Their known failure modes are documented in docs/metrics.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import lexicons as lex
from .text import normalise, rate_per, split_sentences, tokenise

__all__ = ["SyntaxMetrics", "syntax_metrics", "APPROXIMATE_METRICS"]

#: Metrics on this list are heuristics, not measurements.
APPROXIMATE_METRICS = ("passive_voice", "fragments", "subordinate_clauses")

# be-verb (+ optional adverb) + past participle. Catches regular -ed/-en forms
# and a short list of common irregulars.
_IRREGULAR_PARTICIPLES = (
    "done|made|said|seen|known|taken|given|found|held|kept|left|put|read|"
    "run|set|sent|shown|told|thought|understood|written|built|brought|"
    "bought|caught|chosen|cut|dealt|drawn|driven|eaten|fallen|felt|got|"
    "gotten|hit|hurt|led|lost|meant|met|paid|sold|spent|split|spread|"
    "stuck|struck|taught|torn|worn|won"
)
_PASSIVE_RE = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being|get|gets|got)\b"
    r"(?:\s+\w+ly)?\s+"
    r"(?:\w+(?:ed|en)\b|(?:" + _IRREGULAR_PARTICIPLES + r")\b)",
    re.IGNORECASE,
)

_CONTRACTION_RE = re.compile(
    r"\b\w+'(?:t|s|re|ve|ll|d|m)\b", re.IGNORECASE
)

# Verb-shaped suffixes used as a secondary cue in fragment detection.
_VERB_SUFFIX_RE = re.compile(r"\b\w{3,}(?:ed|ing|es|s)\b", re.IGNORECASE)


@dataclass(frozen=True)
class SyntaxMetrics:
    contraction_count: int
    contraction_rate: float
    contraction_preference: float
    first_person_count: int
    first_person_rate: float
    second_person_count: int
    second_person_rate: float
    passive_count: int
    passive_rate: float
    question_count: int
    question_rate: float
    fragment_count: int
    fragment_rate: float
    conjunction_count: int
    conjunction_rate: float
    subordinate_count: int
    subordinate_rate: float
    initial_conjunction_count: int
    initial_conjunction_rate: float
    imperative_count: int
    imperative_rate: float
    strong_modal_rate: float
    weak_modal_rate: float

    def to_dict(self) -> dict:
        return {
            "contraction_count": self.contraction_count,
            "contraction_rate": self.contraction_rate,
            "contraction_preference": self.contraction_preference,
            "first_person_count": self.first_person_count,
            "first_person_rate": self.first_person_rate,
            "second_person_count": self.second_person_count,
            "second_person_rate": self.second_person_rate,
            "passive_count": self.passive_count,
            "passive_rate": self.passive_rate,
            "question_count": self.question_count,
            "question_rate": self.question_rate,
            "fragment_count": self.fragment_count,
            "fragment_rate": self.fragment_rate,
            "conjunction_count": self.conjunction_count,
            "conjunction_rate": self.conjunction_rate,
            "subordinate_count": self.subordinate_count,
            "subordinate_rate": self.subordinate_rate,
            "initial_conjunction_count": self.initial_conjunction_count,
            "initial_conjunction_rate": self.initial_conjunction_rate,
            "imperative_count": self.imperative_count,
            "imperative_rate": self.imperative_rate,
            "strong_modal_rate": self.strong_modal_rate,
            "weak_modal_rate": self.weak_modal_rate,
            "approximate": list(APPROXIMATE_METRICS),
        }


def _contraction_opportunities(tokens: list[str]) -> int:
    """Rough count of places a contraction could have been used.

    "do not", "it is", "we are" and friends. Used for contraction_preference,
    which answers "when you could contract, how often do you?" rather than
    "how many contractions per 100 words", which mostly tracks pronoun use.
    """
    pairs = 0
    subjects = {
        "i", "you", "we", "they", "he", "she", "it", "that", "there",
        "here", "what", "who", "let", "this",
    }
    followers = {"is", "are", "am", "will", "have", "has", "had", "would", "not"}
    negatable = {
        "do", "does", "did", "is", "are", "was", "were", "has", "have", "had",
        "can", "could", "should", "would", "will", "must",
    }
    for a, b in zip(tokens, tokens[1:]):
        if a in subjects and b in followers:
            pairs += 1
        elif a in negatable and b == "not":
            pairs += 1
    return pairs


def _is_fragment(sentence: str, tokens: list[str]) -> bool:
    """Approximate: no finite-verb cue and no verb-shaped token.

    Undercounts badly on fragments built from ordinary verbs ("Running late.")
    and never fires on questions or list items with verbs in them.
    """
    if not tokens:
        return False
    if any(t in lex.FINITE_VERB_CUES for t in tokens):
        return False
    if _VERB_SUFFIX_RE.search(sentence):
        return False
    return True


def syntax_metrics(text: str) -> SyntaxMetrics:
    text = normalise(text)
    tokens = tokenise(text)
    sentences = split_sentences(text)
    words = len(tokens)
    n_sentences = len(sentences) or 1

    contraction_matches = _CONTRACTION_RE.findall(text)
    contractions = sum(
        1 for m in contraction_matches if m.lower() in lex.CONTRACTIONS
    )
    # Fall back to the regex count for contractions not in the lexicon
    # (e.g. "y'know"), minus obvious possessives, which end in "'s" but whose
    # base form is not a known contraction.
    unknown = [
        m for m in contraction_matches
        if m.lower() not in lex.CONTRACTIONS and not m.lower().endswith("'s")
    ]
    contractions += len(unknown)

    opportunities = _contraction_opportunities(tokens) + contractions
    contraction_preference = (
        round(contractions / opportunities, 3) if opportunities else 0.0
    )

    first_person = sum(1 for t in tokens if t in lex.FIRST_PERSON)
    second_person = sum(1 for t in tokens if t in lex.SECOND_PERSON)
    passive = len(_PASSIVE_RE.findall(text))
    questions = sum(1 for s in sentences if s.rstrip().endswith("?"))
    conjunctions = sum(1 for t in tokens if t in lex.COORDINATING_CONJUNCTIONS)
    subordinate = sum(1 for t in tokens if t in lex.SUBORDINATORS)

    initial_conjunction = 0
    imperative = 0
    fragments = 0
    for sentence in sentences:
        sentence_tokens = tokenise(sentence)
        if not sentence_tokens:
            continue
        first = sentence_tokens[0]
        if first in lex.SENTENCE_INITIAL_CONJUNCTIONS:
            initial_conjunction += 1
        if first in lex.IMPERATIVE_OPENERS and not sentence.rstrip().endswith("?"):
            imperative += 1
        if _is_fragment(sentence, sentence_tokens):
            fragments += 1

    strong_modals = sum(1 for t in tokens if t in lex.STRONG_MODALS)
    weak_modals = sum(1 for t in tokens if t in lex.WEAK_MODALS)

    return SyntaxMetrics(
        contraction_count=contractions,
        contraction_rate=rate_per(contractions, words, 100),
        contraction_preference=contraction_preference,
        first_person_count=first_person,
        first_person_rate=rate_per(first_person, words, 100),
        second_person_count=second_person,
        second_person_rate=rate_per(second_person, words, 100),
        passive_count=passive,
        passive_rate=rate_per(passive, n_sentences, 100),
        question_count=questions,
        question_rate=rate_per(questions, n_sentences, 100),
        fragment_count=fragments,
        fragment_rate=rate_per(fragments, n_sentences, 100),
        conjunction_count=conjunctions,
        conjunction_rate=rate_per(conjunctions, words, 100),
        subordinate_count=subordinate,
        subordinate_rate=rate_per(subordinate, n_sentences, 100),
        initial_conjunction_count=initial_conjunction,
        initial_conjunction_rate=rate_per(initial_conjunction, n_sentences, 100),
        imperative_count=imperative,
        imperative_rate=rate_per(imperative, n_sentences, 100),
        strong_modal_rate=rate_per(strong_modals, words, 100),
        weak_modal_rate=rate_per(weak_modals, words, 100),
    )
