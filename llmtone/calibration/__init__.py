"""Questions, word choices, how they are chosen, and the evidence they produce.

``init`` asks a fixed five. ``calibrate`` asks about whatever the profile is
least certain of, using ``selection.py`` -- which decides only *which question
to ask*. Written answers are analysed and scored exactly like any other writing;
A/B word choices touch the vocabulary lists and nothing else.
"""

from .pairs import PAIRS, PAIRS_BY_ID, SKIP, WordChoice
from .questions import (
    ALL_QUESTIONS,
    CALIBRATION_QUESTIONS,
    ONBOARDING_QUESTIONS,
    QUESTIONS_BY_ID,
    Question,
)
from .responses import (
    answered_pair_ids,
    answered_question_ids,
    record_calibration,
    record_choice,
    record_response,
    record_sample,
    verdicts_from_evidence,
)
from .selection import (
    Candidate,
    dimension_priority,
    dimension_uncertainty,
    rank_questions,
    select_pairs,
    select_questions,
)

__all__ = [
    "ONBOARDING_QUESTIONS",
    "CALIBRATION_QUESTIONS",
    "ALL_QUESTIONS",
    "QUESTIONS_BY_ID",
    "Question",
    "Candidate",
    "PAIRS",
    "PAIRS_BY_ID",
    "SKIP",
    "WordChoice",
    "record_response",
    "record_calibration",
    "record_choice",
    "record_sample",
    "answered_question_ids",
    "answered_pair_ids",
    "verdicts_from_evidence",
    "select_questions",
    "select_pairs",
    "rank_questions",
    "dimension_uncertainty",
    "dimension_priority",
]
