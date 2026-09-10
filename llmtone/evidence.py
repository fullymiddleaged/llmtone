"""The evidence log.

llmtone keeps three things strictly separate (see docs/scoring.md):

  evidence   what you actually wrote or chose
  profile    the deterministic interpretation of that evidence
  prompt     the human-readable instructions handed to a model

This module owns the first. The log is append-only JSONL, one record per line,
and it is the source of truth: ``profile.json`` is a derived artifact that can be
deleted and rebuilt from the log at any time. That is what makes the whole
pipeline debuggable -- and what lets a future version rescore old evidence with
better rules without asking you to write anything again.

Raw text is never stored in the log. It lives in ``samples/<id>.txt`` and is
referenced by id.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

__all__ = ["Evidence", "EVIDENCE_KINDS", "append", "load", "new_id"]

#: Kinds of evidence. Phase 1 produces the first two; the rest are the slots
#: that calibration and edit-learning will fill without a schema change.
EVIDENCE_KINDS = (
    "onboarding_response",
    "writing_sample",
    "manual_edit",
    "calibration_choice",
    "observed_edit",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(text: str, kind: str, seq: int) -> str:
    """A short, stable id derived from the content itself.

    Content-derived rather than random so that re-running ``init`` with the same
    answers produces the same evidence ids, and therefore the same profile.
    """
    digest = hashlib.sha256(f"{kind}:{seq}:{text}".encode("utf-8")).hexdigest()
    return f"{kind[:4]}_{digest[:12]}"


@dataclass
class Evidence:
    id: str
    timestamp: str
    kind: str
    source: str
    word_count: int
    text_ref: str | None = None
    prompt: str | None = None
    metrics: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Evidence":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


def append(path: Path, record: Evidence) -> None:
    """Append one record. Creates the file and parent directory if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def load(path: Path) -> list[Evidence]:
    """Read the log. Malformed lines are skipped rather than fatal.

    A corrupt line should cost you one sample, not your whole profile.
    """
    if not path.exists():
        return []
    records: list[Evidence] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(Evidence.from_dict(json.loads(line)))
        except (json.JSONDecodeError, TypeError):
            continue
    return records
