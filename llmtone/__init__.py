"""llmtone -- one voice, any AI.

A local-first writing profile. Analyse how someone actually writes, score it
with rules you can read, and render a portable profile any model can consume.

    from llmtone import analyse, build_profile, render_instructions

Nothing in this package opens a network connection.
"""

from .analysis import Analysis, analyse
from .profile import (
    SCHEMA_VERSION,
    Storage,
    VoiceProfile,
    build_profile,
    render_instructions,
    render_summary,
)
from .scoring import DIMENSIONS, DIMENSION_NAMES, score_all

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Analysis",
    "analyse",
    "VoiceProfile",
    "build_profile",
    "render_summary",
    "render_instructions",
    "Storage",
    "SCHEMA_VERSION",
    "DIMENSIONS",
    "DIMENSION_NAMES",
    "score_all",
]
