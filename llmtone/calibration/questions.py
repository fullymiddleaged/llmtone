"""The onboarding questions.

Deliberately none of them ask you to describe your writing style. People are
poor witnesses to their own prose -- ask someone whether they're formal and
you'll get an aspiration, not an observation. Ask them about their job, or
something that annoyed them, and you get the real thing.

Each question targets a situation likely to expose particular dimensions, noted
in ``targets``. Phase 2's adaptive selection uses that field to choose what to
ask next; Phase 1 simply asks all five.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["Question", "ONBOARDING_QUESTIONS", "MIN_ANSWER_WORDS"]

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

QUESTIONS_BY_ID = {q.id: q for q in ONBOARDING_QUESTIONS}
