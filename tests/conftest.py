from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"

STYLES = ("formal_professional", "casual_direct", "verbose_technical", "warm_conversational")


def read_fixture(name: str) -> str:
    return (FIXTURE_DIR / f"{name}.txt").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def fixtures() -> dict[str, str]:
    return {name: read_fixture(name) for name in STYLES}


@pytest.fixture()
def home(tmp_path: Path) -> Path:
    """An isolated llmtone home. Never touches the real ~/.llmtone."""
    target = tmp_path / "llmtone-home"
    target.mkdir()
    return target
