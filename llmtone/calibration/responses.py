"""Turn an answer or a pasted sample into an evidence record.

Analysis happens here, immediately, so that the metrics are stored alongside the
evidence. That means a later change to the analyser can be spotted by comparing
stored metrics against a fresh analysis of the same text -- the reason the raw
text is kept at all.
"""

from __future__ import annotations

from ..analysis import analyse
from ..evidence import Evidence, new_id, utc_now
from ..profile.storage import Storage
from .questions import Question

__all__ = ["record_response", "record_sample", "summarise_metrics"]


def summarise_metrics(text: str) -> dict:
    """The subset of metrics worth keeping per record.

    Not the whole analysis: the full dump is large, regenerable from the stored
    text, and would triple the size of the evidence log for no benefit.
    """
    analysis = analyse(text)
    return {
        "word_count": analysis.word_count,
        "sentence_count": analysis.basic.sentence_count,
        "features": dict(sorted(analysis.features.items())),
    }


def _record(
    storage: Storage,
    text: str,
    kind: str,
    source: str,
    seq: int,
    prompt: str | None = None,
    meta: dict | None = None,
) -> Evidence:
    text = text.strip()
    metrics = summarise_metrics(text)
    record = Evidence(
        id=new_id(text, kind, seq),
        timestamp=utc_now(),
        kind=kind,
        source=source,
        word_count=metrics["word_count"],
        prompt=prompt,
        metrics=metrics,
        meta=meta or {},
    )
    return storage.add_evidence(record, text=text)


def record_response(
    storage: Storage, question: Question, answer: str, seq: int
) -> Evidence:
    """Store an onboarding answer as evidence."""
    return _record(
        storage,
        answer,
        kind="onboarding_response",
        source=question.id,
        seq=seq,
        prompt=question.text,
        meta={"targets": list(question.targets)},
    )


def record_sample(
    storage: Storage, text: str, source: str, seq: int = 0
) -> Evidence:
    """Store a piece of the user's real writing as evidence."""
    return _record(
        storage,
        text,
        kind="writing_sample",
        source=source,
        seq=seq,
        meta={},
    )
