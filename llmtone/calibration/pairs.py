"""A/B word choices.

The weakest thing in a profile is the ``avoid`` list, because it is inferred
from *absence*: you never wrote "utilise" in 400 words, so perhaps you never
would. That is a guess, and docs/scoring.md says so plainly.

A choice replaces the guess with an observation. Shown "utilise" and "use" and
asked which you would write, you answer in one keystroke, and "you never wrote
this" becomes "you chose the other one".

The bank is generated from the lexicons rather than hand-written twice: every
pair is a formal word that ``vocabulary.py`` already treats as an avoid
candidate, paired with the plain equivalent ``lexicons.FORMAL_TO_PLAIN``
already knows. Edit the lexicon and the bank follows.

Nothing here stores the person's writing -- the words on screen are ours, not
theirs, so a choice is recorded as which of two known words was picked and
nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..analysis import lexicons as lex
from ..analysis.vocabulary import AVOID_CANDIDATES

__all__ = ["WordChoice", "PAIRS", "PAIRS_BY_ID", "SKIP"]

#: What a person picks when they would write neither word. Recorded, because
#: "I'd use neither of those" is itself worth knowing about the formal one.
SKIP = "neither"


@dataclass(frozen=True)
class WordChoice:
    """Two ways of saying the same thing, one of them formal."""

    id: str
    formal: str
    plain: str

    @property
    def options(self) -> tuple[str, str]:
        return (self.formal, self.plain)

    def question(self) -> str:
        return "Which of these would you actually write?"


def _build() -> tuple[WordChoice, ...]:
    """Avoid candidates that have a plain equivalent, in candidate order.

    Candidate order matters: ``AVOID_CANDIDATES`` is already sorted by how
    informative the absence of each word is, so the most useful pairs come
    first and stay first.
    """
    pairs: list[WordChoice] = []
    seen: set[str] = set()
    for candidate in AVOID_CANDIDATES:
        plain = lex.FORMAL_TO_PLAIN.get(candidate)
        if plain is None or candidate in seen:
            continue
        seen.add(candidate)
        pairs.append(
            WordChoice(
                id=f"choice_{candidate.replace(' ', '_').replace('-', '_')}",
                formal=candidate,
                plain=plain,
            )
        )
    return tuple(pairs)


PAIRS: tuple[WordChoice, ...] = _build()

PAIRS_BY_ID: dict[str, WordChoice] = {pair.id: pair for pair in PAIRS}


def _validate() -> None:
    if len(PAIRS_BY_ID) != len(PAIRS):
        raise AssertionError("duplicate pair id")
    if not PAIRS:
        raise AssertionError(
            "no pairs: every AVOID_CANDIDATE lost its FORMAL_TO_PLAIN entry"
        )
    for pair in PAIRS:
        if pair.formal == pair.plain:
            raise AssertionError(f"{pair.id}: both options are the same word")


_validate()
