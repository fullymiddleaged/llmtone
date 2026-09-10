"""Where llmtone keeps things, and how it writes them.

Everything lives under ``~/.llmtone`` (override with ``LLMTONE_HOME``), in plain
files you can read, diff and edit:

    ~/.llmtone/profile.json      the derived profile
    ~/.llmtone/evidence.jsonl    the append-only source of truth
    ~/.llmtone/samples/*.txt     your writing, exactly as you pasted it

No account, no database, no sync. Nothing in this module opens a socket.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..evidence import Evidence, append as append_evidence, load as load_evidence
from .model import VoiceProfile
from .schema import validate_or_raise

__all__ = ["Storage", "default_home"]

ENV_HOME = "LLMTONE_HOME"


def default_home() -> Path:
    """The llmtone home directory, honouring ``LLMTONE_HOME``."""
    override = os.environ.get(ENV_HOME)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".llmtone"


def _write_private(path: Path, text: str) -> None:
    """Write atomically, and keep the file to the owner where the OS allows it.

    Atomic because a half-written profile.json is worse than no profile at all:
    the temp file is only renamed over the target once it is fully written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    )
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path = Path(handle.name)
        try:
            os.chmod(temp_path, 0o600)
        except OSError:  # pragma: no cover - platform dependent
            pass
        os.replace(temp_path, path)
    except BaseException:  # pragma: no cover - cleanup path
        Path(handle.name).unlink(missing_ok=True)
        raise


@dataclass(frozen=True)
class Storage:
    home: Path

    @classmethod
    def open(cls, home: Path | str | None = None) -> "Storage":
        return cls(home=Path(home).expanduser() if home else default_home())

    # --- paths ------------------------------------------------------------
    @property
    def profile_path(self) -> Path:
        return self.home / "profile.json"

    @property
    def evidence_path(self) -> Path:
        return self.home / "evidence.jsonl"

    @property
    def samples_dir(self) -> Path:
        return self.home / "samples"

    def sample_path(self, sample_id: str) -> Path:
        return self.samples_dir / f"{sample_id}.txt"

    # --- profile ----------------------------------------------------------
    def profile_exists(self) -> bool:
        return self.profile_path.exists()

    def save_profile(self, profile: VoiceProfile) -> Path:
        """Validate against the published schema, then write atomically.

        Validating on the way out means a malformed profile is caught here,
        where the fix is obvious, rather than in whatever tool consumes it.
        """
        data = profile.to_dict()
        validate_or_raise(data)
        _write_private(
            self.profile_path,
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        )
        return self.profile_path

    def load_profile(self) -> VoiceProfile | None:
        if not self.profile_exists():
            return None
        data = json.loads(self.profile_path.read_text(encoding="utf-8"))
        return VoiceProfile.from_dict(data)

    # --- evidence and samples ---------------------------------------------
    def add_evidence(self, record: Evidence, text: str | None = None) -> Evidence:
        """Append an evidence record, storing its text as a sample if given."""
        if text is not None:
            self.samples_dir.mkdir(parents=True, exist_ok=True)
            _write_private(self.sample_path(record.id), text)
            record.text_ref = f"samples/{record.id}.txt"
        append_evidence(self.evidence_path, record)
        return record

    def evidence(self) -> list[Evidence]:
        return load_evidence(self.evidence_path)

    def sample_texts(self) -> list[str]:
        """Every stored sample, in evidence order."""
        return [text for text, _ in self.labelled_sample_texts()]

    def labelled_sample_texts(self) -> list[tuple[str, str | None]]:
        """Every stored sample with its context label, in evidence order.

        Order matters: the corpus is the samples concatenated, and a stable
        order is what makes the resulting profile reproducible. The label comes
        off the evidence record, so relabelling means adding evidence rather
        than editing a profile.
        """
        samples: list[tuple[str, str | None]] = []
        for record in self.evidence():
            if not record.text_ref:
                continue
            path = self.home / record.text_ref
            if path.exists():
                samples.append((
                    path.read_text(encoding="utf-8"),
                    record.meta.get("context"),
                ))
        return samples
