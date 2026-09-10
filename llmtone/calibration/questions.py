"""The question bank: onboarding, and the larger calibration set.

Deliberately none of them ask you to describe your writing style. People are
poor witnesses to their own prose -- ask someone whether they're formal and
you'll get an aspiration, not an observation. Ask them about their job, or
something that annoyed them, and you get the real thing.

Each question targets a situation likely to expose particular dimensions, noted
in ``targets``, most-exposed first. ``init`` asks the five onboarding questions
in order; ``calibrate`` picks from the larger bank below according to which
dimensions the profile is least certain about (see ``selection.py``).

``targets`` is the load-bearing field, and it is written by hand. ``text`` and
``hint`` are only wording -- a later version may let a model rewrite those for
the person being asked -- but nothing chooses a question's targets except this
file, and no part of this produces a score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "Question",
    "ONBOARDING_QUESTIONS",
    "CALIBRATION_QUESTIONS",
    "ALL_QUESTIONS",
    "QUESTIONS_BY_ID",
    "MIN_ANSWER_WORDS",
]

#: Answers shorter than this are too small to analyse usefully, so the CLI
#: nudges (but never refuses -- a short honest answer beats a padded one).
MIN_ANSWER_WORDS = 15


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    hint: str
    targets: tuple[str, ...] = field(default=())


ONBOARDING_QUESTIONS: tuple[Question, ...] = (
    Question(
        id="onboarding_work",
        text=(
            "What do you actually do for work? Describe it to someone who "
            "knows nothing about it."
        ),
        hint="A few sentences is plenty.",
        targets=("technicality", "formality", "conciseness"),
    ),
    Question(
        id="onboarding_interest",
        text=(
            "Tell us about something you're really interested in. What makes "
            "it interesting to you?"
        ),
        hint="Whatever comes to mind first.",
        targets=("warmth", "humour", "conversationality"),
    ),
    Question(
        id="onboarding_disagreement",
        text=(
            "Someone at work suggests something you think is a bad idea. "
            "What would you say to them?"
        ),
        hint="Write what you'd actually send, not what you'd like to send.",
        targets=("directness", "hedging", "formality"),
    ),
    Question(
        id="onboarding_annoyance",
        text="Tell us about something you've dealt with recently that annoyed you.",
        hint="Go on, be honest.",
        targets=("humour", "conversationality", "warmth"),
    ),
    Question(
        id="onboarding_explanation",
        text=(
            "Explain something you're good at as if you're explaining it to a "
            "reasonably intelligent friend."
        ),
        hint="Pick anything -- it doesn't have to be work.",
        targets=("technicality", "conciseness", "directness"),
    ),
)
#: The calibration bank. Larger than the onboarding set and never asked in
#: order: ``calibrate`` selects from it. Same rule as onboarding -- every
#: question asks about a situation, never about the person's own style. The
#: situations are chosen so that each dimension is the first target of at least
#: two of them, or selection would have nothing to offer when that dimension is
#: the uncertain one.
CALIBRATION_QUESTIONS: tuple[Question, ...] = (
    Question(
        id="calib_bad_news",
        text=(
            "You have to tell a client that a deadline has slipped by two "
            "weeks. Write the message you would send."
        ),
        hint="Their fault, your fault, nobody's fault -- your call.",
        targets=("directness", "hedging", "formality"),
    ),
    Question(
        id="calib_thanks",
        text=(
            "Someone on your team stayed late to fix something that wasn't "
            "their mess. Write what you'd send them."
        ),
        hint="However you'd actually say it.",
        targets=("warmth", "conversationality", "humour"),
    ),
    Question(
        id="calib_handover",
        text=(
            "Write the notes you'd leave for whoever covers your job while "
            "you're away for a week."
        ),
        hint="The things that would actually go wrong.",
        targets=("conciseness", "technicality", "directness"),
    ),
    Question(
        id="calib_recommendation",
        text=(
            "Recommend something to a friend -- a book, a place, a tool, "
            "anything -- and say why."
        ),
        hint="Sell it to them.",
        targets=("conversationality", "warmth", "humour"),
    ),
    Question(
        id="calib_pushback",
        text=(
            "Your manager asks for something on a timeline you think is "
            "unrealistic. Write your reply."
        ),
        hint="What you'd send, not what you'd mutter.",
        targets=("hedging", "directness", "formality"),
    ),
    Question(
        id="calib_meeting_summary",
        text=(
            "Summarise the last meeting you sat through for someone who "
            "missed it."
        ),
        hint="Any meeting. It doesn't have to have been a good one.",
        targets=("conciseness", "formality", "technicality"),
    ),
    Question(
        id="calib_complaint",
        text=(
            "Something you ordered or paid for went wrong. Write the message "
            "you'd send about it."
        ),
        hint="A real one, if you have it to hand.",
        targets=("directness", "formality", "warmth"),
    ),
    Question(
        id="calib_rough_week",
        text=(
            "A friend tells you they've had a rotten week. Write what you'd "
            "send back."
        ),
        hint="Whatever you'd genuinely say, including if it's a joke.",
        targets=("warmth", "conversationality", "hedging"),
    ),
    Question(
        id="calib_went_wrong",
        text=(
            "Tell the story of something that went badly wrong and how it got "
            "sorted out in the end."
        ),
        hint="The version you'd tell in the pub.",
        targets=("humour", "conversationality", "warmth"),
    ),
    Question(
        id="calib_teach",
        text=(
            "Someone new to your field asks how one part of it works. Write "
            "your first reply to them."
        ),
        hint="Pick the thing you get asked about most.",
        targets=("technicality", "warmth", "conciseness"),
    ),
    Question(
        id="calib_estimate",
        text=(
            "Someone asks how long a piece of work will take, and you don't "
            "really know yet. Write your answer."
        ),
        hint="Be honest about how you actually handle this one.",
        targets=("hedging", "conversationality", "directness"),
    ),
    Question(
        id="calib_introduction",
        text="Introduce yourself in a channel or group you've just joined.",
        hint="First message, cold room.",
        targets=("formality", "warmth", "humour"),
    ),
    Question(
        id="calib_decision_note",
        text=(
            "Write the note explaining a decision you made recently to people "
            "who weren't part of making it."
        ),
        hint="Work or otherwise.",
        targets=("formality", "conciseness", "hedging"),
    ),
    Question(
        id="calib_no_time",
        text=(
            "A colleague asks whether you can look at something today, and you "
            "can't. Write the reply."
        ),
        hint="Short is fine -- short is rather the point.",
        targets=("conversationality", "conciseness", "directness"),
    ),
    Question(
        id="calib_unpopular_view",
        text=(
            "What does nearly everyone in your field believe that you think is "
            "wrong? Make the case."
        ),
        hint="Go on.",
        targets=("directness", "technicality", "hedging"),
    ),
    Question(
        id="calib_jargon",
        text=(
            "Explain a piece of jargon from your work to someone outside it -- "
            "and say whether it's worth keeping."
        ),
        hint="Bonus points for one you hate.",
        targets=("technicality", "humour", "directness"),
    ),
    Question(
        id="calib_bad_writing",
        text=(
            "Describe the worst piece of corporate writing you've had to read "
            "lately."
        ),
        hint="Be unkind about it.",
        targets=("humour", "warmth", "conversationality"),
    ),
)

ALL_QUESTIONS: tuple[Question, ...] = ONBOARDING_QUESTIONS + CALIBRATION_QUESTIONS

QUESTIONS_BY_ID: dict[str, Question] = {q.id: q for q in ALL_QUESTIONS}


def _validate() -> None:
    """Catch a duplicated id or a typo'd dimension at import, not at runtime."""
    from ..scoring import DIMENSION_NAMES

    if len(QUESTIONS_BY_ID) != len(ALL_QUESTIONS):
        raise AssertionError("duplicate question id")
    for question in ALL_QUESTIONS:
        unknown = set(question.targets) - set(DIMENSION_NAMES)
        if unknown:
            raise AssertionError(f"{question.id}: unknown targets {sorted(unknown)}")
        if len(set(question.targets)) != len(question.targets):
            raise AssertionError(f"{question.id}: repeated target")


_validate()
