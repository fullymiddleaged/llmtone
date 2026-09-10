"""Choosing what to ask next.

Onboarding asks five fixed questions. Calibration asks about the dimensions the
profile is least sure of, which means the second session is not a repeat of the
first: if warmth is already settled and hedging is not, you get asked about
hedging.

Three numbers decide it, and all three are readable:

  uncertainty  how much of the confidence this dimension could reach is missing
  importance   how much it matters to get this dimension right at all
  saturation   how many questions have already been aimed at it

  priority = uncertainty x importance / (1 + saturation)

**Uncertainty is measured against the dimension's ceiling, not against 1.0.**
Humour can never exceed 0.55 confidence (see docs/scoring.md), so on raw
``1 - confidence`` it would look like the most uncertain dimension forever and
every question would be aimed at a thing word-counting cannot see. Measuring
the gap to what is actually achievable stops calibration chasing its own tail.

Selection is greedy and re-ranks after each pick: once a question aimed at
warmth is chosen, warmth is treated as more saturated for the rest of the round,
so a round of three questions spreads across three weak dimensions rather than
asking the same thing three ways.

Nothing here writes a score. It chooses which question to put on the screen,
and the answer is then analysed exactly like any other piece of writing.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..scoring import DIMENSIONS_BY_NAME
from .pairs import PAIRS, WordChoice
from .questions import CALIBRATION_QUESTIONS, QUESTIONS_BY_ID, Question

__all__ = [
    "Candidate",
    "dimension_uncertainty",
    "dimension_priority",
    "rank_questions",
    "select_questions",
    "select_pairs",
    "TARGET_DECAY",
    "DEFAULT_ROUND",
]

#: A question's second target exposes a dimension less reliably than its first,
#: and its third less again. Geometric rather than a cliff, because a secondary
#: target is still real evidence.
TARGET_DECAY = 0.6

#: How many questions a calibration round asks unless told otherwise. Enough to
#: move a dimension, few enough that people finish.
DEFAULT_ROUND = 3

#: Weight of an already-answered question when counting how saturated a
#: dimension is. Lower than 1.0 because evidence is never quite enough:
#: answering one warmth question does not close warmth for good.
ASKED_WEIGHT = 1.0


@dataclass(frozen=True)
class Candidate:
    """A question, its priority, and why it got that priority."""

    question: Question
    priority: float
    per_target: dict[str, float]

    def reason(self) -> str:
        """The dimensions this question was picked for, strongest first."""
        ranked = sorted(self.per_target.items(), key=lambda kv: (-kv[1], kv[0]))
        return ", ".join(name for name, value in ranked if value > 0.0)


def dimension_uncertainty(profile) -> dict[str, float]:
    """How far each dimension is from the best confidence it could reach.

    1.0 means nothing is known; 0.0 means it is as certain as this dimension
    can honestly get. ``profile`` may be ``None`` -- before ``init`` there is
    nothing known about anything.
    """
    out: dict[str, float] = {}
    for name, dimension in DIMENSIONS_BY_NAME.items():
        ceiling = dimension.confidence_ceiling
        confidence = 0.0
        if profile is not None:
            score = profile.style.get(name)
            if score is not None:
                confidence = score.confidence
        gap = (ceiling - confidence) / ceiling
        out[name] = round(max(0.0, min(1.0, gap)), 4)
    return out


def _saturation(asked_ids) -> dict[str, float]:
    """How heavily each dimension has already been asked about.

    Counts every question already answered, weighting its targets by position
    the same way scoring a candidate does -- a question that merely touched
    warmth third does not count as having covered warmth.
    """
    counts: dict[str, float] = {name: 0.0 for name in DIMENSIONS_BY_NAME}
    for question_id in asked_ids:
        question = QUESTIONS_BY_ID.get(question_id)
        if question is None:  # a sample, or a question from another version
            continue
        for position, target in enumerate(question.targets):
            if target in counts:
                counts[target] += ASKED_WEIGHT * TARGET_DECAY ** position
    return counts


def dimension_priority(
    profile, asked_ids: tuple[str, ...] | list[str] = ()
) -> dict[str, float]:
    """How much each dimension is worth asking about, most first.

    The same number the question ranking is built from, exposed on its own so
    that the CLI can tell you what it is chasing without guessing at it. A
    dimension can be very uncertain and still rank low: humour is capped so far
    below the others that chasing it would waste the questions.
    """
    uncertainty = dimension_uncertainty(profile)
    saturation = _saturation(asked_ids)
    return {
        name: round(
            uncertainty[name]
            * dimension.calibration_importance
            / (1.0 + saturation.get(name, 0.0)),
            6,
        )
        for name, dimension in DIMENSIONS_BY_NAME.items()
    }


def _score_question(
    question: Question,
    uncertainty: dict[str, float],
    saturation: dict[str, float],
) -> tuple[float, dict[str, float]]:
    per_target: dict[str, float] = {}
    for position, target in enumerate(question.targets):
        dimension = DIMENSIONS_BY_NAME.get(target)
        if dimension is None:  # pragma: no cover - guarded at import
            continue
        value = (
            uncertainty.get(target, 1.0)
            * dimension.calibration_importance
            * TARGET_DECAY ** position
            / (1.0 + saturation.get(target, 0.0))
        )
        per_target[target] = round(value, 6)
    return round(sum(per_target.values()), 6), per_target


def rank_questions(
    profile,
    *,
    asked_ids: tuple[str, ...] | list[str] = (),
    bank: tuple[Question, ...] = CALIBRATION_QUESTIONS,
) -> list[Candidate]:
    """Every unasked question in the bank, best first.

    Ties break on question id, so the same profile and the same history always
    produce the same order -- selection is as deterministic as scoring.
    """
    uncertainty = dimension_uncertainty(profile)
    saturation = _saturation(asked_ids)
    already = set(asked_ids)

    candidates = []
    for question in bank:
        if question.id in already:
            continue
        priority, per_target = _score_question(question, uncertainty, saturation)
        candidates.append(Candidate(question, priority, per_target))
    candidates.sort(key=lambda c: (-c.priority, c.question.id))
    return candidates


def select_questions(
    profile,
    *,
    asked_ids: tuple[str, ...] | list[str] = (),
    count: int = DEFAULT_ROUND,
    bank: tuple[Question, ...] = CALIBRATION_QUESTIONS,
) -> list[Candidate]:
    """Pick ``count`` questions, re-ranking after each one.

    Re-ranking is what stops a round asking three variations of the same
    question: choosing a warmth question makes warmth count as saturated for
    the rest of the round.
    """
    history = list(asked_ids)
    chosen: list[Candidate] = []
    for _ in range(max(0, count)):
        ranked = rank_questions(profile, asked_ids=history, bank=bank)
        if not ranked:
            break
        pick = ranked[0]
        chosen.append(pick)
        history.append(pick.question.id)
    return chosen


def select_pairs(
    profile,
    *,
    asked_ids: tuple[str, ...] | list[str] = (),
    count: int = DEFAULT_ROUND,
    bank: tuple[WordChoice, ...] = PAIRS,
) -> list[WordChoice]:
    """Pick which word choices to offer.

    The rule is the useful one: ask first about the words the profile has
    already guessed you avoid. Those entries are inferred from absence, which
    docs/scoring.md calls the weakest thing in the profile -- so calibration
    spends its questions confirming exactly the claims it is least sure of,
    and only then works through the rest of the bank in order.
    """
    already = set(asked_ids)
    guessed = []
    if profile is not None:
        guessed = list(profile.vocabulary.get("avoid", []))
    confirmed = []
    if profile is not None:
        confirmed = list(profile.notes.get("avoid_confirmed_by_choice", []))
    pending = [w for w in guessed if w not in confirmed]

    unasked = [pair for pair in bank if pair.id not in already]
    unasked.sort(key=lambda pair: (pair.formal not in pending, bank.index(pair)))
    return unasked[: max(0, count)]
