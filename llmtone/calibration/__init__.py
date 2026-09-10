"""Onboarding questions, and the evidence they produce.

Phase 1 asks a fixed set of five. Adaptive selection -- choosing what to ask
based on which dimensions are least certain -- is Phase 2, and will live beside
these as ``selection.py``.
"""

from .questions import ONBOARDING_QUESTIONS, Question
from .responses import record_response, record_sample

__all__ = ["ONBOARDING_QUESTIONS", "Question", "record_response", "record_sample"]
