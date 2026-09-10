"""Profile building, schema validation, storage and determinism."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from llmtone.evidence import Evidence, new_id, utc_now
from llmtone.profile import (
    SCHEMA_VERSION,
    Storage,
    VoiceProfile,
    build_profile,
    validate,
    validate_or_raise,
)
from llmtone.profile.schema import SchemaError

FIXED = {
    "profile_id": "test0000",
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
}


def make(texts: list[str]) -> VoiceProfile:
    return build_profile(texts, **FIXED)


class TestDeterminism:
    def test_same_input_gives_an_identical_profile(self, fixtures):
        texts = list(fixtures.values())
        assert make(texts).to_json() == make(texts).to_json()

    def test_identical_across_a_fresh_interpreter(self, fixtures, tmp_path):
        """Guards against set or dict iteration order leaking into output.

        Python randomises string hashing per process, so a value derived from
        set ordering can look stable in-process and still differ between runs.
        """
        repo_root = Path(__file__).resolve().parents[1]
        script = tmp_path / "build.py"
        script.write_text(
            "\n".join([
                "import sys",
                f"sys.path[:0] = [{str(repo_root)!r}, {str(Path(__file__).parent)!r}]",
                "from conftest import STYLES, read_fixture",
                "from llmtone.profile import build_profile",
                "texts = [read_fixture(s) for s in STYLES]",
                f"print(build_profile(texts, **{FIXED!r}).to_json())",
            ]),
            encoding="utf-8",
        )
        runs = [
            subprocess.run(
                [sys.executable, str(script)],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            for _ in range(2)
        ]
        assert runs[0] == runs[1]

    def test_sample_order_is_the_only_thing_that_matters(self, fixtures):
        """Not an accident: the corpus is the samples concatenated in order."""
        a, b = fixtures["casual_direct"], fixtures["formal_professional"]
        assert make([a, b]).to_json() != make([b, a]).to_json()


class TestBuildProfile:
    def test_shape(self, fixtures):
        profile = make([fixtures["casual_direct"]])
        assert profile.version == SCHEMA_VERSION
        assert set(profile.style) == {
            "formality", "directness", "warmth", "conciseness",
            "humour", "hedging", "technicality", "conversationality",
        }

    def test_metadata_counts_words_and_samples(self, fixtures):
        profile = make([fixtures["casual_direct"], fixtures["warm_conversational"]])
        assert profile.metadata["sample_count"] == 2
        assert profile.metadata["word_count"] > 500

    def test_empty_input_produces_a_valid_zero_profile(self):
        profile = make([])
        assert profile.metadata["word_count"] == 0
        assert validate(profile.to_dict()) == []
        assert all(s.confidence == 0.0 for s in profile.style.values())

    def test_structure_reflects_the_writing(self, fixtures):
        bulleted = make([fixtures["casual_direct"]])
        prose = make([fixtures["verbose_technical"]])
        order = ["low", "medium", "high"]
        assert order.index(bulleted.structure["bullet_preference"]) > order.index(
            prose.structure["bullet_preference"]
        )
        sizes = ["short", "medium", "long"]
        assert sizes.index(prose.structure["paragraph_length"]) > sizes.index(
            bulleted.structure["paragraph_length"]
        )

    def test_notes_record_the_caveats(self, fixtures):
        profile = make([fixtures["casual_direct"]])
        assert profile.notes["avoid_inferred_from_absence"] is True
        assert "passive_voice" in profile.notes["approximate_metrics"]
        assert "personality" in profile.notes["describes"]

    def test_phrasing_avoided_is_empty_in_phase_one(self, fixtures):
        """Phrases you avoid need edit evidence, which Phase 1 has none of."""
        assert make([fixtures["casual_direct"]]).phrasing["avoided"] == []


class TestSchema:
    def test_every_fixture_profile_validates(self, fixtures):
        for text in fixtures.values():
            validate_or_raise(make([text]).to_dict())

    def test_round_trip(self, fixtures):
        profile = make([fixtures["casual_direct"]])
        restored = VoiceProfile.from_dict(json.loads(profile.to_json()))
        assert restored.to_json() == profile.to_json()

    def test_rejects_a_value_out_of_range(self, fixtures):
        data = make([fixtures["casual_direct"]]).to_dict()
        data["style"]["formality"]["value"] = 150
        errors = validate(data)
        assert any("above maximum" in e for e in errors)

    def test_rejects_a_bad_punctuation_band(self, fixtures):
        data = make([fixtures["casual_direct"]]).to_dict()
        data["punctuation"]["semicolon"] = "sometimes"
        assert any("not one of" in e for e in validate(data))

    def test_reports_every_problem_not_just_the_first(self, fixtures):
        data = make([fixtures["casual_direct"]]).to_dict()
        data["style"]["formality"]["value"] = 150
        data["style"]["warmth"]["confidence"] = 3.0
        with pytest.raises(SchemaError) as excinfo:
            validate_or_raise(data)
        assert len(excinfo.value.errors) >= 2

    def test_missing_required_key_is_caught(self):
        assert any("missing required key" in e for e in validate({"version": "1.0"}))

    def test_the_wheel_ships_the_schema_where_the_loader_looks_for_it(self):
        """Ties pyproject to schema.py so they cannot drift apart.

        In a source checkout the schema is found at the repository root. In an
        installed wheel that root does not exist, so hatchling force-includes
        the file into the package. If someone changes either side of that
        arrangement, an installed llmtone stops being able to validate.
        """
        from llmtone.profile.schema import _CANDIDATES

        root = Path(__file__).resolve().parents[1]
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")

        installed_location = _CANDIDATES[0]
        package_dir = installed_location.parent.name
        expected = f'"voice-profile.schema.json" = "{package_dir}/{installed_location.name}"'
        assert "[tool.hatch.build.targets.wheel.force-include]" in pyproject
        assert expected in pyproject

        # And the checkout path is the one actually in use right now.
        assert _CANDIDATES[1] == root / "voice-profile.schema.json"
        assert _CANDIDATES[1].exists()

    def test_a_boolean_is_not_a_number(self, fixtures):
        data = make([fixtures["casual_direct"]]).to_dict()
        data["style"]["formality"]["value"] = True
        assert any("boolean" in e for e in validate(data))


class TestStorage:
    def test_round_trip_through_disk(self, home, fixtures):
        storage = Storage.open(home)
        saved = make([fixtures["casual_direct"]])
        storage.save_profile(saved)
        assert storage.load_profile().to_json() == saved.to_json()

    def test_load_returns_none_when_absent(self, home):
        assert Storage.open(home).load_profile() is None

    def test_saving_an_invalid_profile_raises_before_writing(self, home, fixtures):
        storage = Storage.open(home)
        profile = make([fixtures["casual_direct"]])
        profile.style["formality"].__dict__["value"] = 999
        with pytest.raises(SchemaError):
            storage.save_profile(profile)
        assert not storage.profile_exists()

    def test_evidence_is_appended_and_text_stored_separately(self, home):
        storage = Storage.open(home)
        record = Evidence(
            id=new_id("hello there", "writing_sample", 0),
            timestamp=utc_now(),
            kind="writing_sample",
            source="test",
            word_count=2,
        )
        storage.add_evidence(record, text="hello there")

        assert storage.sample_texts() == ["hello there"]
        line = storage.evidence_path.read_text(encoding="utf-8")
        assert "hello there" not in line  # raw text never enters the log
        assert record.id in line

    def test_evidence_ids_are_content_derived_and_stable(self):
        assert new_id("same text", "writing_sample", 0) == new_id(
            "same text", "writing_sample", 0
        )
        assert new_id("a", "writing_sample", 0) != new_id("b", "writing_sample", 0)

    def test_a_corrupt_log_line_costs_one_sample_not_the_profile(self, home):
        storage = Storage.open(home)
        storage.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        storage.evidence_path.write_text(
            '{"id":"a","timestamp":"t","kind":"writing_sample","source":"s",'
            '"word_count":1}\n'
            "{ this is not json\n",
            encoding="utf-8",
        )
        assert len(storage.evidence()) == 1

    def test_profile_is_rebuildable_from_evidence_alone(self, home, fixtures):
        storage = Storage.open(home)
        record = Evidence(
            id=new_id(fixtures["casual_direct"], "writing_sample", 0),
            timestamp=utc_now(), kind="writing_sample", source="t",
            word_count=0,
        )
        storage.add_evidence(record, text=fixtures["casual_direct"])
        storage.save_profile(make(storage.sample_texts()))

        first = storage.load_profile().to_json()
        storage.profile_path.unlink()
        storage.save_profile(make(storage.sample_texts()))
        assert storage.load_profile().to_json() == first
