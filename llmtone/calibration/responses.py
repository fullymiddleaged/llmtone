"""Turn an answer or a pasted sample into an evidence record.

Analysis happens here, immediately, so that the metrics are stored alongside the
evidence. That means a later change to the analyser can be spotted by comparing
stored metrics against a fresh analysis of the same text -- the reason the raw
text is kept at all.
"""

from __future__ import annotations

from ..analysis import analyse
from ..evidence import Evidence, new_id, utc_now
from ..profile.model import WordVerdict, normalise_context
from ..profile.storage import Storage
from .pairs import SKIP, WordChoice
from .questions import QUESTIONS_BY_ID, Question

__all__ = [
    "record_response",
    "record_calibration",
    "record_sample",
    "summarise_metrics",
    "answered_question_ids",
    "record_choice",
    "answered_pair_ids",
    "verdicts_from_evidence",
]


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


def record_calibration(
    storage: Storage, question: Question, answer: str, seq: int
) -> Evidence:
    """Store an answer to an adaptively chosen question.

    Identical treatment to an onboarding answer -- it is analysed the same way
    and scored the same way. The kind is separate only so that a later version
    can tell which questions were chosen for you and judge whether choosing
    them helped.
    """
    return _record(
        storage,
        answer,
        kind="calibration_response",
        source=question.id,
        seq=seq,
        prompt=question.text,
        meta={"targets": list(question.targets)},
    )


def answered_question_ids(records: list[Evidence]) -> list[str]:
    """Question ids already answered, oldest first, without duplicates.

    Read from the evidence log rather than tracked separately: the log is the
    source of truth about what has been asked, as it is about everything else.
    """
    seen: list[str] = []
    for record in records:
        if record.source in QUESTIONS_BY_ID and record.source not in seen:
            seen.append(record.source)
    return seen


def record_choice(
    storage: Storage, pair: WordChoice, chosen: str | None, seq: int
) -> Evidence:
    """Store an answered A/B word choice.

    No sample file is written. The words on screen came from our lexicon, not
    from this person, so there is nothing of theirs to store -- the record is
    which of two known words was picked, and that is all it will ever be.
    """
    picked = chosen if chosen in pair.options else None
    record = Evidence(
        id=new_id(f"{pair.id}:{picked or SKIP}", "calibration_choice", seq),
        timestamp=utc_now(),
        kind="calibration_choice",
        source=pair.id,
        word_count=0,
        prompt=pair.question(),
        metrics={},
        meta={
            "formal": pair.formal,
            "plain": pair.plain,
            "chosen": picked,
        },
    )
    return storage.add_evidence(record)


def answered_pair_ids(records: list[Evidence]) -> list[str]:
    """Pair ids already answered, oldest first, without duplicates."""
    seen: list[str] = []
    for record in records:
        if record.kind == "calibration_choice" and record.source not in seen:
            seen.append(record.source)
    return seen


def verdicts_from_evidence(records: list[Evidence]) -> list[WordVerdict]:
    """Every answered choice, in log order, ready for ``build_profile``.

    Read back out of the log rather than tracked anywhere: the profile has to
    stay a function of the evidence, choices included.
    """
    verdicts: list[WordVerdict] = []
    for record in records:
        if record.kind != "calibration_choice":
            continue
        formal = record.meta.get("formal")
        plain = record.meta.get("plain")
        if not formal or not plain:  # a record from a future kind of choice
            continue
        verdicts.append(
            WordVerdict(formal=formal, plain=plain, chosen=record.meta.get("chosen"))
        )
    return verdicts


def record_sample(
    storage: Storage,
    text: str,
    source: str,
    seq: int = 0,
    context: str | None = None,
) -> Evidence:
    """Store a piece of the user's real writing as evidence.

    ``context`` is where this was written -- work, casual, whatever the person
    calls it. It rides on the evidence record rather than the profile, so the
    profile stays a pure function of the log and a context can be added to old
    writing by appending, never by editing.
    """
    return _record(
        storage,
        text,
        kind="writing_sample",
        source=source,
        seq=seq,
        meta={"context": normalise_context(context)} if context else {},
    )
