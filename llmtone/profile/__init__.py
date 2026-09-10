"""The voice profile: model, schema, storage and rendering."""

from .model import (
    MIN_CONTEXT_WORDS,
    PARAGRAPH_BANDS,
    SCHEMA_VERSION,
    DimensionScore,
    VoiceProfile,
    build_profile,
    normalise_context,
)
from .render import (
    CONFIDENCE_THRESHOLD,
    describe_dimension,
    render_instructions,
    render_summary,
)
from .schema import SCHEMA_PATH, SchemaError, load_schema, validate, validate_or_raise
from .storage import Storage, default_home

__all__ = [
    "VoiceProfile",
    "DimensionScore",
    "build_profile",
    "SCHEMA_VERSION",
    "PARAGRAPH_BANDS",
    "MIN_CONTEXT_WORDS",
    "normalise_context",
    "Storage",
    "default_home",
    "SchemaError",
    "SCHEMA_PATH",
    "load_schema",
    "validate",
    "validate_or_raise",
    "render_summary",
    "render_instructions",
    "describe_dimension",
    "CONFIDENCE_THRESHOLD",
]
