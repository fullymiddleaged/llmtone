"""The voice profile: its in-memory form, and how evidence becomes one.

``build_profile`` is the single place where analysis and scoring meet. It takes
texts and returns a profile; it does no I/O and holds no state, so the same
inputs always produce the same profile, byte for byte.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from ..analysis import Analysis, analyse
from ..analysis.punctuation import MARKS
from ..analysis.vocabulary import LIST_LIMIT
from ..scoring import DIMENSIONS, DimensionResult, contradictions, score_all

__all__ = [
    "VoiceProfile",
    "MIN_CONTEXT_WORDS",
    "PRESET_CONTEXTS",
    "normalise_context",
    "DimensionScore",
    "WordVerdict",
    "build_profile",
    "SCHEMA_VERSION",
    "PARAGRAPH_BANDS",
]

SCHEMA_VERSION = "1.0"

#: Punctuation marks reported in the profile. The analyser tracks more; these
#: are the ones that actually distinguish one writer from another.
PROFILE_MARKS = (
    "semicolon", "em_dash", "en_dash", "colon", "parentheses",
    "exclamation", "ellipsis", "hyphen", "comma", "question",
)

#: Average words per paragraph -> label.
PARAGRAPH_BANDS = ((45.0, "short"), (90.0, "medium"))

#: Headings or bullets per paragraph -> label.
STRUCTURE_BANDS = ((0.08, "low"), (0.30, "medium"))

#: How samples are joined into one corpus: a blank line, so the analyser sees
#: paragraph boundaries rather than one run-on block.
PARAGRAPH_SEPARATOR = "\n\n"

#: A labelled context needs this much writing before it gets its own entry.
#: Below it every dimension would score under the 0.45 threshold anyway, so the
#: entry would be a heading with nothing under it.
MIN_CONTEXT_WORDS = 200

#: The tones onboarding offers by default, in the order it asks for them.
#: They are only a starting set -- any label works -- but naming them means a
#: person ends up with several contexts without having to invent the idea of a
#: context first. Nothing here creates a context on its own: a context exists
#: when there is writing labelled with it, and not before.
PRESET_CONTEXTS = ("business", "friendly", "marketing", "code")


def normalise_context(label: str) -> str:
    """A context label as it is stored: lowercase, no spaces.

    Labels become JSON keys and are typed by hand at a prompt, so "Work" and
    "work" have to be the same context or a profile quietly grows two of them.
    """
    return "-".join(label.strip().lower().split())


def _band(value: float, bands: tuple[tuple[float, str], ...], top: str) -> str:
    for threshold, label in bands:
        if value <= threshold:
            return label
    return top


@dataclass(frozen=True)
class WordVerdict:
    """One answered A/B word choice.

    ``chosen`` is the word the person said they would write, or ``None`` if
    they would write neither. Either way this is evidence of *preference*,
    which is what the absence-based ``avoid`` list has never had.
    """

    formal: str
    plain: str
    chosen: str | None

    @property
    def avoids_formal(self) -> bool:
        return self.chosen != self.formal


@dataclass(frozen=True)
class DimensionScore:
    value: int
    confidence: float

    def to_dict(self) -> dict:
        return {"value": self.value, "confidence": self.confidence}


@dataclass
class VoiceProfile:
    version: str
    profile_id: str
    style: dict[str, DimensionScore]
    syntax: dict
    punctuation: dict[str, str]
    vocabulary: dict[str, list[str]]
    phrasing: dict[str, list[str]]
    structure: dict[str, str]
    contexts: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    notes: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "profile_id": self.profile_id,
            "style": {
                name: score.to_dict() for name, score in self.style.items()
            },
            "syntax": self.syntax,
            "punctuation": self.punctuation,
            "vocabulary": self.vocabulary,
            "phrasing": self.phrasing,
            "structure": self.structure,
            "contexts": self.contexts,
            "metadata": self.metadata,
            "notes": self.notes,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "VoiceProfile":
        style = {
            name: DimensionScore(
                value=int(entry["value"]), confidence=float(entry["confidence"])
            )
            for name, entry in data.get("style", {}).items()
        }
        return cls(
            version=data.get("version", SCHEMA_VERSION),
            profile_id=data.get("profile_id", ""),
            style=style,
            syntax=data.get("syntax", {}),
            punctuation=data.get("punctuation", {}),
            vocabulary=data.get("vocabulary", {}),
            phrasing=data.get("phrasing", {}),
            structure=data.get("structure", {}),
            contexts=data.get("contexts", {}),
            metadata=data.get("metadata", {}),
            notes=data.get("notes", {}),
        )

    def for_context(self, name: str) -> "VoiceProfile":
        """This profile as it applies in one context.

        A context entry is a partial profile: the dimensions it overrides and
        nothing else. Everything it does not mention -- punctuation, vocabulary,
        structure -- is the same person, so it comes from the top level. An
        unknown name returns the profile unchanged rather than raising, because
        asking for a context nobody has evidence for is not an error.
        """
        entry = self.contexts.get(normalise_context(name))
        if not entry:
            return self
        style = dict(self.style)
        for dimension, score in (entry.get("style") or {}).items():
            style[dimension] = DimensionScore(
                value=int(score["value"]), confidence=float(score["confidence"])
            )
        return replace(self, style=style)

    def confident(self, threshold: float) -> list[str]:
        """Dimension names whose confidence is at or above ``threshold``."""
        return [
            name for name, score in self.style.items()
            if score.confidence >= threshold
        ]


def _score_texts(
    texts: list[str],
) -> tuple[dict[str, DimensionResult], Analysis]:
    """Analyse a group of texts as one corpus, and score it.

    The corpus is the texts joined, so a 2000-word document naturally outweighs
    a 20-word note without any weighting arithmetic; each text is also analysed
    alone so the scorer can measure consistency across them. One function, used
    for the whole corpus and for each context, so a context is never scored by
    a slightly different rule.
    """
    analyses = [analyse(t) for t in texts]
    corpus = analyse(PARAGRAPH_SEPARATOR.join(texts)) if texts else analyse("")
    results = score_all(
        corpus.features,
        corpus.word_count,
        [(a.features, a.word_count) for a in analyses],
    )
    return results, corpus


def _style(results: dict[str, DimensionResult]) -> dict[str, DimensionScore]:
    return {
        d.name: DimensionScore(
            value=results[d.name].value, confidence=results[d.name].confidence
        )
        for d in DIMENSIONS
    }


def _context_profiles(
    labelled: list[tuple[str, str | None]],
) -> dict[str, dict]:
    """One partial profile per labelled context with enough writing behind it.

    Only ``style`` and ``metadata``: a context is how someone shifts register,
    not a different person, so their punctuation and vocabulary stay at the top
    level. Contexts are scored by exactly the same code as the whole corpus --
    including confidence -- so a thin context reports itself as thin rather than
    being silently trusted.

    Sorted by name so the file diffs cleanly.
    """
    grouped: dict[str, list[str]] = {}
    for text, label in labelled:
        if not label:  # unlabelled is unknown, not a context of its own
            continue
        grouped.setdefault(normalise_context(label), []).append(text)

    contexts: dict[str, dict] = {}
    for name in sorted(grouped):
        results, corpus = _score_texts(grouped[name])
        if corpus.word_count < MIN_CONTEXT_WORDS:
            continue
        contexts[name] = {
            "style": {n: s.to_dict() for n, s in _style(results).items()},
            "metadata": {
                "sample_count": len(grouped[name]),
                "word_count": corpus.word_count,
            },
        }
    return contexts


def build_profile(
    texts: list[str],
    *,
    profile_id: str,
    created_at: str,
    updated_at: str,
    sample_count: int | None = None,
    verdicts: "Sequence[WordVerdict]" = (),
    labels: "Sequence[str | None]" = (),
) -> VoiceProfile:
    """Build a profile from writing samples and any answered word choices.

    The corpus is analysed as one document (so counts are exact rather than
    averaged), and each sample is analysed separately so the scorer can measure
    how consistent the person is across them.

    ``verdicts`` are answered A/B choices. They touch the vocabulary lists only:
    a word someone chose against is real evidence of avoidance, and it displaces
    the guesses the ``avoid`` list is otherwise made of. No dimension value or
    confidence moves -- a stated preference is not observed behaviour, and the
    scorer stays a function of the writing alone.

    ``labels`` is a context name per text, positionally aligned with ``texts``
    and padded with ``None``. A labelled context with enough writing behind it
    gets its own entry in ``contexts``; everything else is unaffected, so a
    profile with no labels at all is byte-identical to one built before
    contexts existed.
    """
    labelled = [
        (text, labels[index] if index < len(labels) else None)
        for index, text in enumerate(texts)
        if text and text.strip()
    ]
    texts = [text for text, _ in labelled]
    results, corpus = _score_texts(texts)
    style = _style(results)

    punctuation = {
        mark: corpus.punctuation.bands[mark]
        for mark in PROFILE_MARKS
        if mark in corpus.punctuation.bands
    }

    paragraphs = max(corpus.basic.paragraph_count, 1)
    structure = {
        "paragraph_length": _band(
            corpus.basic.average_paragraph_length, PARAGRAPH_BANDS, "long"
        ),
        "heading_preference": _band(
            corpus.basic.heading_count / paragraphs, STRUCTURE_BANDS, "high"
        ),
        "bullet_preference": _band(
            corpus.basic.bullet_count / paragraphs, STRUCTURE_BANDS, "high"
        ),
    }

    vocab = corpus.vocabulary
    chosen_against: list[str] = []
    chosen_for: list[str] = []
    for verdict in verdicts:
        target = chosen_against if verdict.avoids_formal else chosen_for
        other = chosen_for if verdict.avoids_formal else chosen_against
        if verdict.formal in other:  # answered again, differently: latest wins
            other.remove(verdict.formal)
        if verdict.formal not in target:
            target.append(verdict.formal)

    # Confirmed avoidance first, and it displaces guesses rather than adding to
    # them: a list of twelve words is only useful if the best evidence is at the
    # top of it.
    inferred = [
        word for word in vocab.avoid
        if word not in chosen_against and word not in chosen_for
    ]
    avoid = chosen_against + inferred[: max(0, LIST_LIMIT - len(chosen_against))]
    prefer = vocab.prefer + [w for w in chosen_for if w not in vocab.prefer]

    return VoiceProfile(
        version=SCHEMA_VERSION,
        profile_id=profile_id,
        style=style,
        syntax={
            "average_sentence_length": corpus.basic.average_sentence_length,
            "sentence_length_variance": corpus.basic.sentence_length_variance,
            "average_paragraph_length": corpus.basic.average_paragraph_length,
            "contraction_preference": corpus.syntax.contraction_preference,
            "fragment_preference": round(corpus.syntax.fragment_rate / 100, 3),
            "question_preference": round(corpus.syntax.question_rate / 100, 3),
            "passive_preference": round(corpus.syntax.passive_rate / 100, 3),
            "vocabulary_diversity": corpus.basic.vocabulary_diversity,
        },
        punctuation=punctuation,
        vocabulary={
            "prefer": prefer,
            "avoid": avoid,
            "technical_terms": vocab.technical_terms,
            "colloquialisms": vocab.colloquialisms,
        },
        phrasing={
            # Phase 1 can only observe phrases you used. Phrases you avoid need
            # edit evidence, which arrives with feedback learning in Phase 3.
            "preferred": corpus.phrases,
            "avoided": [],
        },
        structure=structure,
        contexts=_context_profiles(labelled),
        metadata={
            "sample_count": sample_count if sample_count is not None else len(texts),
            "word_count": corpus.word_count,
            "sentence_count": corpus.basic.sentence_count,
            "created_at": created_at,
            "updated_at": updated_at,
            "generator": "llmtone",
            "scoring_version": SCHEMA_VERSION,
        },
        notes={
            "approximate_metrics": list(corpus.to_dict()["approximate_metrics"]),
            # True only while some entry is still a guess. Consumers use this to
            # decide how hard to enforce the list.
            "avoid_inferred_from_absence": bool(
                [w for w in avoid if w not in chosen_against]
            ),
            "avoid_confirmed_by_choice": [w for w in avoid if w in chosen_against],
            # Dimensions the samples disagree about by more than
            # CONTEXT_SPREAD_POINTS. Empty means checked and none found, which
            # is a different claim from a missing key.
            "varies_by_context": [v.to_dict() for v in contradictions(results)],
            "describes": "writing behaviour only, not personality",
        },
    )


def _unused_marks_guard() -> None:  # pragma: no cover - documentation helper
    """PROFILE_MARKS must all be marks the analyser actually tracks."""
    unknown = set(PROFILE_MARKS) - set(MARKS)
    if unknown:
        raise AssertionError(f"unknown punctuation marks: {sorted(unknown)}")


_unused_marks_guard()
