"""The voice profile: its in-memory form, and how evidence becomes one.

``build_profile`` is the single place where analysis and scoring meet. It takes
texts and returns a profile; it does no I/O and holds no state, so the same
inputs always produce the same profile, byte for byte.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..analysis import Analysis, analyse
from ..analysis.punctuation import MARKS
from ..scoring import DIMENSIONS, DimensionResult, score_all

__all__ = [
    "VoiceProfile",
    "DimensionScore",
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


def _band(value: float, bands: tuple[tuple[float, str], ...], top: str) -> str:
    for threshold, label in bands:
        if value <= threshold:
            return label
    return top


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

    def confident(self, threshold: float) -> list[str]:
        """Dimension names whose confidence is at or above ``threshold``."""
        return [
            name for name, score in self.style.items()
            if score.confidence >= threshold
        ]


def build_profile(
    texts: list[str],
    *,
    profile_id: str,
    created_at: str,
    updated_at: str,
    sample_count: int | None = None,
) -> VoiceProfile:
    """Build a profile from writing samples.

    The corpus is analysed as one document (so counts are exact rather than
    averaged), and each sample is analysed separately so the scorer can measure
    how consistent the person is across them.
    """
    texts = [t for t in texts if t and t.strip()]
    corpus_text = "\n\n".join(texts)
    corpus: Analysis = analyse(corpus_text) if corpus_text else analyse("")
    per_sample: list[Analysis] = [analyse(t) for t in texts]

    results: dict[str, DimensionResult] = score_all(
        corpus.features,
        corpus.word_count,
        [(a.features, a.word_count) for a in per_sample],
    )

    style = {
        d.name: DimensionScore(
            value=results[d.name].value, confidence=results[d.name].confidence
        )
        for d in DIMENSIONS
    }

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
            "prefer": vocab.prefer,
            "avoid": vocab.avoid,
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
        contexts={},
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
            "avoid_inferred_from_absence": True,
            "describes": "writing behaviour only, not personality",
        },
    )


def _unused_marks_guard() -> None:  # pragma: no cover - documentation helper
    """PROFILE_MARKS must all be marks the analyser actually tracks."""
    unknown = set(PROFILE_MARKS) - set(MARKS)
    if unknown:
        raise AssertionError(f"unknown punctuation marks: {sorted(unknown)}")


_unused_marks_guard()
