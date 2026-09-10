"""The privacy guarantees, asserted rather than promised.

docs/privacy.md claims llmtone contains no network code and never logs raw
writing. These tests are what keep that true as the code changes.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from llmtone.analysis import analyse
from llmtone.calibration import record_sample
from llmtone.profile import Storage, build_profile

PACKAGE = Path(__file__).resolve().parents[1] / "llmtone"

#: Anything that could open a connection or start a subprocess.
FORBIDDEN_MODULES = {
    "socket", "ssl", "http", "urllib", "urllib2", "ftplib", "smtplib",
    "telnetlib", "requests", "httpx", "aiohttp", "urllib3", "xmlrpc",
    "asyncio", "subprocess", "webbrowser", "ctypes",
}

SECRET = "Correct-Horse-Battery-Staple-2026"


def _imported_modules() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                modules.add(node.module.split(".")[0])
        found[str(path.relative_to(PACKAGE))] = modules
    return found


class TestNoNetworkCode:
    def test_no_module_imports_anything_that_could_open_a_connection(self):
        offenders = {
            name: sorted(modules & FORBIDDEN_MODULES)
            for name, modules in _imported_modules().items()
            if modules & FORBIDDEN_MODULES
        }
        assert offenders == {}

    def test_the_package_declares_no_runtime_dependencies(self):
        pyproject = (PACKAGE.parent / "pyproject.toml").read_text(encoding="utf-8")
        assert "dependencies = []" in pyproject


class TestWritingIsNotLeaked:
    """What is and is not retained.

    The guarantee is about *prose*, not about every word: llmtone keeps no
    sentences, but distinctive individual words are exactly what a vocabulary
    profile is made of. docs/privacy.md says so, and these tests pin both
    halves so the claim cannot quietly become wrong in either direction.
    """

    SENTENCE = "The quarterly reconciliation ran overnight without incident."

    def test_no_sentence_survives_into_the_metric_dump(self):
        dump = json.dumps(analyse(self.SENTENCE).to_dict()).lower()
        assert self.SENTENCE.lower() not in dump
        # Nor any three-word run from it.
        words = self.SENTENCE.lower().rstrip(".").split()
        for i in range(len(words) - 2):
            assert " ".join(words[i:i + 3]) not in dump

    def test_individual_distinctive_words_do_appear(self):
        """Documented, not a leak: this is what the vocabulary lists are."""
        dump = json.dumps(analyse(f"{SECRET} appeared here once.").to_dict())
        assert SECRET.lower() in dump.lower()

    def test_the_evidence_log_references_text_rather_than_holding_it(self, home):
        storage = Storage.open(home)
        record_sample(storage, f"{SECRET} was written here.", source="test")
        assert SECRET not in storage.evidence_path.read_text(encoding="utf-8")

    def test_samples_are_stored_verbatim_and_are_deletable(self, home):
        storage = Storage.open(home)
        record = record_sample(storage, f"{SECRET} was written here.", source="test")
        sample = storage.sample_path(record.id)
        assert SECRET in sample.read_text(encoding="utf-8")

        sample.unlink()
        assert storage.sample_texts() == []

    def test_domain_identifiers_can_reach_the_profile(self, fixtures):
        """Not a leak, but users should know before sharing a profile.

        The profile's word lists are style vocabulary and a curated avoid list,
        so ordinary content words do not reach it. Shape-detected technical
        terms do -- and those are exactly the things (internal service names,
        filenames) someone might not want to hand over. docs/privacy.md says
        so; this test keeps the claim and the behaviour together.
        """
        text = fixtures["casual_direct"] + (
            "\n\nThe acmeLedger service reads billing_secrets.py on startup. "
            "The acmeLedger service is the one that matters here."
        )
        profile = build_profile(
            [text], profile_id="p", created_at="c", updated_at="u"
        )
        terms = json.dumps(profile.vocabulary["technical_terms"])
        assert "acmeledger" in terms.lower()
        assert "billing_secrets.py" in terms.lower()

    def test_ordinary_content_words_do_not_reach_the_profile(self, fixtures):
        """A voice profile is style, not subject matter."""
        text = fixtures["casual_direct"] + (
            f"\n\n{SECRET} {SECRET} {SECRET} was mentioned repeatedly."
        )
        profile = build_profile(
            [text], profile_id="p", created_at="c", updated_at="u"
        )
        assert SECRET.lower() not in json.dumps(profile.to_dict()).lower()


class TestStorageIsInspectable:
    def test_everything_written_is_plain_text(self, home):
        storage = Storage.open(home)
        record_sample(storage, "Some ordinary writing goes here.", source="t")
        storage.save_profile(
            build_profile(
                storage.sample_texts(), profile_id="p", created_at="c", updated_at="u"
            )
        )
        for path in sorted(home.rglob("*")):
            if path.is_file():
                path.read_text(encoding="utf-8")  # raises if it is not text

    @pytest.mark.parametrize("name", ["profile.json", "evidence.jsonl"])
    def test_files_land_where_documented(self, home, name):
        storage = Storage.open(home)
        record_sample(storage, "Words here.", source="t")
        storage.save_profile(
            build_profile(["Words here."], profile_id="p", created_at="c", updated_at="u")
        )
        assert (home / name).exists()
