"""The command line, driven end to end against a temporary home."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmtone.calibration import ONBOARDING_QUESTIONS
from llmtone.cli import EXIT_ERROR, EXIT_NOT_YET, EXIT_OK, bar, main
from llmtone.profile import Storage

FIXTURES = Path(__file__).parent / "fixtures"

ANSWERS = {
    "onboarding_work": (
        "I look after the deployment pipeline for a mid-sized product team. "
        "Mostly that means keeping the build green and stopping things from "
        "falling over at four in the morning."
    ),
    "onboarding_interest": (
        "I've got really into bread lately. It's the same three ingredients "
        "every time and it still goes wrong in about nine different ways, "
        "which I find weirdly satisfying."
    ),
    "onboarding_disagreement": (
        "I'd say something like: I don't think that'll work, and here's why. "
        "Then I'd give them the specific reason rather than just being "
        "negative about it."
    ),
    "onboarding_annoyance": (
        "The expenses system. Three weeks to approve a train ticket and it "
        "logs you out every time you upload a receipt. Absolute nightmare."
    ),
    "onboarding_explanation": (
        "Debugging is mostly narrowing things down. You find the last point "
        "where it definitely worked, the first point where it definitely "
        "didn't, and then you keep halving the gap until there's nowhere left "
        "for the bug to hide."
    ),
}


@pytest.fixture()
def answers_file(tmp_path: Path) -> Path:
    path = tmp_path / "answers.json"
    path.write_text(json.dumps(ANSWERS, indent=2), encoding="utf-8")
    return path


def run(args, home: Path) -> int:
    return main(["--home", str(home), *args])


def init(home: Path, answers_file: Path, sample: str = "casual_direct") -> int:
    return run(
        ["init", "--answers", str(answers_file),
         "--sample", str(FIXTURES / f"{sample}.txt")],
        home,
    )


class TestBar:
    def test_bar_is_full_at_100_and_empty_at_0(self):
        assert bar(100) == "█" * 10
        assert bar(0) == "░" * 10

    def test_bar_is_always_the_requested_width(self):
        assert all(len(bar(v)) == 10 for v in range(0, 101))


class TestInit:
    def test_creates_a_profile_and_evidence(self, home, answers_file, capsys):
        assert init(home, answers_file) == EXIT_OK
        storage = Storage.open(home)
        assert storage.profile_exists()

        evidence = storage.evidence()
        assert len(evidence) == len(ONBOARDING_QUESTIONS) + 1
        assert sum(1 for e in evidence if e.kind == "writing_sample") == 1

        output = capsys.readouterr().out
        assert "Your Voice Profile" in output
        assert "Don't rewrite it first" in output

    def test_profile_validates_against_the_schema(self, home, answers_file):
        init(home, answers_file)
        from llmtone.profile import validate

        data = json.loads((home / "profile.json").read_text(encoding="utf-8"))
        assert validate(data) == []

    def test_refuses_to_clobber_an_existing_profile(self, home, answers_file, capsys):
        init(home, answers_file)
        assert init(home, answers_file) == EXIT_ERROR
        assert "already exists" in capsys.readouterr().out

    def test_force_starts_over(self, home, answers_file):
        init(home, answers_file)
        assert run(
            ["init", "--force", "--answers", str(answers_file),
             "--sample", str(FIXTURES / "formal_professional.txt")],
            home,
        ) == EXIT_OK

    def test_samples_are_stored_as_plain_readable_files(self, home, answers_file):
        init(home, answers_file)
        samples = list((home / "samples").glob("*.txt"))
        assert len(samples) == len(ONBOARDING_QUESTIONS) + 1
        assert "expenses system" in "".join(
            p.read_text(encoding="utf-8") for p in samples
        )

    def test_running_init_twice_with_the_same_answers_gives_the_same_profile(
        self, tmp_path, answers_file
    ):
        outputs = []
        for name in ("a", "b"):
            home = tmp_path / name
            home.mkdir()
            init(home, answers_file)
            data = json.loads((home / "profile.json").read_text(encoding="utf-8"))
            for key in ("profile_id", "created_at", "updated_at"):
                data.get("metadata", {}).pop(key, None)
                data.pop(key, None)
            outputs.append(json.dumps(data, sort_keys=True))
        assert outputs[0] == outputs[1]


class TestAnalyse:
    def test_reports_metrics_without_a_profile(self, home, capsys):
        assert run(["analyse", str(FIXTURES / "casual_direct.txt")], home) == EXIT_OK
        output = capsys.readouterr().out
        assert "Words" in output
        assert "approximations" in output
        assert not Storage.open(home).profile_exists()

    def test_json_output_is_machine_readable(self, home, capsys):
        run(["analyse", "--json", str(FIXTURES / "casual_direct.txt")], home)
        payload = json.loads(capsys.readouterr().out)
        assert payload["basic"]["word_count"] > 0
        assert "passive_voice" in payload["approximate_metrics"]

    def test_save_adds_the_file_to_the_profile(self, home, answers_file):
        init(home, answers_file)
        before = Storage.open(home).load_profile().metadata["word_count"]
        run(["analyse", "--save", str(FIXTURES / "verbose_technical.txt")], home)
        after = Storage.open(home).load_profile().metadata["word_count"]
        assert after > before

    def test_missing_file_is_an_error_not_a_traceback(self, home, capsys):
        assert run(["analyse", str(home / "nope.txt")], home) == EXIT_ERROR
        assert "No such file" in capsys.readouterr().out

    def test_analyze_spelling_is_accepted(self, home):
        assert run(["analyze", str(FIXTURES / "casual_direct.txt")], home) == EXIT_OK


class TestProfileAndPrompt:
    def test_profile_shows_bars_and_confidence(self, home, answers_file, capsys):
        init(home, answers_file)
        capsys.readouterr()
        assert run(["profile"], home) == EXIT_OK
        output = capsys.readouterr().out
        assert "Directness" in output
        assert "conf" in output
        assert "█" in output or "░" in output

    def test_prompt_produces_usable_instructions(self, home, answers_file, capsys):
        init(home, answers_file)
        capsys.readouterr()
        assert run(["prompt"], home) == EXIT_OK
        output = capsys.readouterr().out
        assert "Write in this person's voice" in output
        assert "Do not imitate" in output

    def test_export_is_valid_json(self, home, answers_file, capsys):
        init(home, answers_file)
        capsys.readouterr()
        assert run(["export"], home) == EXIT_OK
        assert json.loads(capsys.readouterr().out)["version"] == "1.0"

    def test_export_to_a_file(self, home, answers_file, tmp_path):
        init(home, answers_file)
        target = tmp_path / "out.json"
        assert run(["export", "-o", str(target)], home) == EXIT_OK
        assert json.loads(target.read_text(encoding="utf-8"))["style"]

    @pytest.mark.parametrize("command", ["profile", "prompt", "export"])
    def test_commands_needing_a_profile_say_so(self, home, capsys, command):
        assert run([command], home) == EXIT_ERROR
        assert "Run `llmtone init` first" in capsys.readouterr().out


class TestUnbuiltCommands:
    def test_check_exits_distinctly_and_explains(self, home, capsys):
        assert run(["check", "some.txt"], home) == EXIT_NOT_YET
        assert "Phase 3" in capsys.readouterr().out


class TestDifferentWritersDifferentOutput:
    def test_two_writers_get_visibly_different_profiles(self, tmp_path, answers_file):
        prompts = {}
        for name, sample in (("a", "casual_direct"), ("b", "formal_professional")):
            home = tmp_path / name
            home.mkdir()
            init(home, answers_file, sample=sample)
            profile = Storage.open(home).load_profile()
            prompts[name] = profile.style["formality"].value
        assert prompts["b"] > prompts["a"]
