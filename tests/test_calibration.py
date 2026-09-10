"""Question selection, and the calibrate command.

Selection decides which question appears on the screen. It never produces a
value or a confidence, so these tests are about ordering and coverage, not
about numbers moving in a particular direction.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmtone.calibration import (
    ALL_QUESTIONS,
    CALIBRATION_QUESTIONS,
    PAIRS,
    QUESTIONS_BY_ID,
    SKIP,
    dimension_uncertainty,
    rank_questions,
    select_pairs,
    select_questions,
)
from llmtone.calibration.responses import (
    answered_pair_ids,
    answered_question_ids,
    verdicts_from_evidence,
)
from llmtone.analysis.vocabulary import AVOID_CANDIDATES
from llmtone.cli import EXIT_ERROR, EXIT_OK, main
from llmtone.profile import Storage
from llmtone.profile.model import DimensionScore, VoiceProfile
from llmtone.scoring import DIMENSION_NAMES, DIMENSIONS_BY_NAME

from test_cli import ANSWERS  # shares the scripted onboarding answers

FIXTURES = Path(__file__).parent / "fixtures"


def make_profile(**confidences: float) -> VoiceProfile:
    """A profile with the given confidences, and 0.60 for everything else."""
    style = {
        name: DimensionScore(value=50, confidence=confidences.get(name, 0.60))
        for name in DIMENSION_NAMES
    }
    return VoiceProfile(
        version="1.0",
        profile_id="test",
        style=style,
        syntax={},
        punctuation={},
        vocabulary={},
        phrasing={},
        structure={},
    )


class TestQuestionBank:
    def test_every_dimension_has_at_least_two_questions_aimed_at_it(self):
        primary = [q.targets[0] for q in CALIBRATION_QUESTIONS]
        for name in DIMENSION_NAMES:
            assert primary.count(name) >= 2, f"{name} has nowhere to go"

    def test_ids_are_unique_and_targets_are_real_dimensions(self):
        assert len(QUESTIONS_BY_ID) == len(ALL_QUESTIONS)
        for question in ALL_QUESTIONS:
            assert question.targets
            assert set(question.targets) <= set(DIMENSION_NAMES)

    def test_no_question_asks_about_writing_style(self):
        """The whole premise: ask about situations, never about their prose."""
        banned = ("your writing", "your style", "your tone", "how do you write")
        for question in ALL_QUESTIONS:
            lowered = question.text.lower()
            assert not any(phrase in lowered for phrase in banned)


class TestUncertainty:
    def test_nothing_known_means_everything_is_uncertain(self):
        assert set(dimension_uncertainty(None).values()) == {1.0}

    def test_measured_against_the_ceiling_not_against_one(self):
        """Humour caps at 0.55, so 0.55 confidence is as done as it can get."""
        profile = make_profile(humour=0.55, formality=0.55)
        uncertainty = dimension_uncertainty(profile)
        assert uncertainty["humour"] == 0.0
        assert uncertainty["formality"] > 0.3

    def test_a_confident_dimension_is_less_uncertain_than_a_shaky_one(self):
        uncertainty = dimension_uncertainty(make_profile(warmth=0.10, hedging=0.80))
        assert uncertainty["warmth"] > uncertainty["hedging"]


class TestRanking:
    def test_the_weakest_dimension_gets_asked_about_first(self):
        profile = make_profile(hedging=0.02)
        top = rank_questions(profile)[0].question
        assert top.targets[0] == "hedging"

    def test_already_answered_questions_are_never_offered_again(self):
        asked = [q.id for q in CALIBRATION_QUESTIONS[:5]]
        offered = {
            c.question.id for c in rank_questions(make_profile(), asked_ids=asked)
        }
        assert offered.isdisjoint(asked)

    def test_answering_about_a_dimension_pushes_it_down_the_queue(self):
        profile = make_profile(warmth=0.05)
        first = rank_questions(profile)[0]
        assert first.question.targets[0] == "warmth"

        after = rank_questions(profile, asked_ids=[first.question.id])
        # Warmth is still weak, so it may well come up again -- but not at the
        # same priority, because it has now been asked about once.
        assert after[0].priority < first.priority

    def test_humour_loses_to_dimensions_worth_more(self):
        """Equally uncertain on paper; humour is worth less, so it waits."""
        assert DIMENSIONS_BY_NAME["humour"].calibration_importance < 1.0
        ranked = rank_questions(make_profile())
        assert ranked[0].question.targets[0] != "humour"

    def test_ranking_is_deterministic(self):
        profile = make_profile(warmth=0.3, humour=0.2)
        runs = [
            [c.question.id for c in rank_questions(profile, asked_ids=["calib_teach"])]
            for _ in range(3)
        ]
        assert runs[0] == runs[1] == runs[2]

    def test_ties_break_on_id(self):
        ranked = rank_questions(make_profile())
        tied = [c for c in ranked if c.priority == ranked[0].priority]
        assert [c.question.id for c in tied] == sorted(c.question.id for c in tied)

    def test_a_candidate_can_explain_itself(self):
        candidate = rank_questions(make_profile(hedging=0.01))[0]
        assert "hedging" in candidate.reason()


class TestSelection:
    def test_a_round_spreads_across_different_dimensions(self):
        chosen = select_questions(make_profile(), count=3)
        primaries = [c.question.targets[0] for c in chosen]
        assert len(set(primaries)) == 3

    def test_it_never_offers_the_same_question_twice_in_a_round(self):
        chosen = select_questions(make_profile(), count=6)
        assert len({c.question.id for c in chosen}) == len(chosen)

    def test_it_runs_out_gracefully(self):
        everything = [q.id for q in CALIBRATION_QUESTIONS]
        assert select_questions(make_profile(), asked_ids=everything, count=3) == []

    def test_count_zero_asks_nothing(self):
        assert select_questions(make_profile(), count=0) == []


class TestAnsweredQuestionIds:
    def test_reads_question_ids_out_of_the_evidence_log(self, home, tmp_path):
        answers = tmp_path / "answers.json"
        answers.write_text(json.dumps(ANSWERS), encoding="utf-8")
        main(
            ["--home", str(home), "init", "--answers", str(answers),
             "--sample", str(FIXTURES / "casual_direct.txt")]
        )
        asked = answered_question_ids(Storage.open(home).evidence())
        assert set(asked) == set(ANSWERS)
        assert all(question_id in QUESTIONS_BY_ID for question_id in asked)


ANSWER_TEXT = (
    "Honestly it depends on the day, but I would probably just say what I "
    "think and then get on with it. There's not much point dressing it up "
    "when everyone involved already knows roughly where things stand, and "
    "the longer you leave it the worse the conversation gets."
)

CALIBRATION_ANSWERS = {q.id: ANSWER_TEXT for q in CALIBRATION_QUESTIONS}


@pytest.fixture()
def calibration_answers(tmp_path: Path) -> Path:
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps(CALIBRATION_ANSWERS), encoding="utf-8")
    return path


@pytest.fixture()
def all_choices(tmp_path: Path) -> Path:
    """Every pair answered with the plain word."""
    path = tmp_path / "choices.json"
    path.write_text(
        json.dumps({pair.id: pair.plain for pair in PAIRS}), encoding="utf-8"
    )
    return path


@pytest.fixture()
def initialised(home: Path, tmp_path: Path) -> Path:
    answers = tmp_path / "onboarding.json"
    answers.write_text(json.dumps(ANSWERS), encoding="utf-8")
    main(
        ["--home", str(home), "init", "--answers", str(answers),
         "--sample", str(FIXTURES / "casual_direct.txt")]
    )
    return home


def calibrate(home: Path, *args: str) -> int:
    return main(["--home", str(home), "calibrate", *args])


class TestCalibrateCommand:
    def test_it_needs_a_profile_first(self, home, capsys):
        assert calibrate(home) == EXIT_ERROR
        assert "Run `llmtone init` first" in capsys.readouterr().out

    def test_dry_run_shows_the_questions_and_writes_nothing(self, initialised, capsys):
        before = Storage.open(initialised).evidence()
        assert calibrate(initialised, "--dry-run") == EXIT_OK
        output = capsys.readouterr().out
        assert "Would ask 3" in output
        assert Storage.open(initialised).evidence() == before

    def test_it_says_why_it_picked_each_question(
        self, initialised, calibration_answers, capsys
    ):
        assert calibrate(initialised, "--answers", str(calibration_answers)) == EXIT_OK
        assert "asking because" in capsys.readouterr().out

    def test_answers_become_evidence_and_rebuild_the_profile(
        self, initialised, calibration_answers
    ):
        storage = Storage.open(initialised)
        before = storage.load_profile()
        assert calibrate(
            initialised, "--answers", str(calibration_answers), "-n", "2"
        ) == EXIT_OK

        added = [e for e in storage.evidence() if e.kind == "calibration_response"]
        assert len(added) == 2
        assert all(e.text_ref for e in added)

        after = storage.load_profile()
        assert after.metadata["word_count"] > before.metadata["word_count"]
        assert after.metadata["sample_count"] > before.metadata["sample_count"]
        assert after.profile_id == before.profile_id

    def test_it_never_asks_the_same_question_across_rounds(
        self, initialised, calibration_answers
    ):
        calibrate(initialised, "--answers", str(calibration_answers), "-n", "3")
        first = answered_question_ids(Storage.open(initialised).evidence())
        calibrate(initialised, "--answers", str(calibration_answers), "-n", "3")
        second = answered_question_ids(Storage.open(initialised).evidence())
        assert len(second) == len(set(second))
        assert len(second) == len(first) + 3

    def test_it_stops_when_both_banks_are_exhausted(
        self, initialised, calibration_answers, all_choices, capsys
    ):
        for _ in range(5):
            calibrate(initialised, "--answers", str(calibration_answers), "-n", "4",
                      "--choices", str(all_choices), "--pairs", "20")
        capsys.readouterr()
        assert calibrate(
            initialised, "--answers", str(calibration_answers),
            "--choices", str(all_choices)
        ) == EXIT_OK
        assert "answered everything in the bank" in capsys.readouterr().out

    def test_it_carries_on_with_word_choices_when_questions_run_out(
        self, initialised, calibration_answers, capsys
    ):
        for _ in range(5):
            calibrate(initialised, "--answers", str(calibration_answers), "-n", "4",
                      "--pairs", "0")
        capsys.readouterr()
        assert calibrate(initialised, "--pairs", "2", "--dry-run") == EXIT_OK
        assert "word choices only" in capsys.readouterr().out

    def test_it_reports_what_the_answers_changed(
        self, initialised, calibration_answers, capsys
    ):
        calibrate(initialised, "--answers", str(calibration_answers), "-n", "3")
        output = capsys.readouterr().out
        assert "What that changed" in output or "No dimension moved" in output

    def test_the_profile_still_validates_afterwards(
        self, initialised, calibration_answers
    ):
        from llmtone.profile import validate

        calibrate(initialised, "--answers", str(calibration_answers), "-n", "3")
        data = json.loads((initialised / "profile.json").read_text(encoding="utf-8"))
        assert validate(data) == []

    def test_the_same_answers_give_the_same_profile(self, tmp_path, calibration_answers):
        onboarding = tmp_path / "onboarding.json"
        onboarding.write_text(json.dumps(ANSWERS), encoding="utf-8")
        profiles = []
        for name in ("a", "b"):
            home = tmp_path / name
            home.mkdir()
            main(
                ["--home", str(home), "init", "--answers", str(onboarding),
                 "--sample", str(FIXTURES / "casual_direct.txt")]
            )
            calibrate(home, "--answers", str(calibration_answers), "-n", "3")
            profile = Storage.open(home).load_profile()
            profiles.append({n: s.to_dict() for n, s in profile.style.items()})
        assert profiles[0] == profiles[1]


class TestWordChoiceBank:
    def test_every_pair_is_an_avoid_candidate_with_a_plain_equivalent(self):
        for pair in PAIRS:
            assert pair.formal in AVOID_CANDIDATES
            assert pair.plain and pair.plain != pair.formal

    def test_pair_ids_are_unique(self):
        assert len({pair.id for pair in PAIRS}) == len(PAIRS)

    def test_it_asks_first_about_words_the_profile_only_guessed(self):
        profile = make_profile()
        profile.vocabulary = {"avoid": ["optimal"]}
        profile.notes = {}
        assert select_pairs(profile, count=1)[0].formal == "optimal"

    def test_answered_pairs_are_not_offered_again(self):
        asked = [pair.id for pair in PAIRS[:3]]
        offered = {pair.id for pair in select_pairs(None, asked_ids=asked, count=5)}
        assert offered.isdisjoint(asked)

    def test_selection_is_deterministic(self):
        runs = [[p.id for p in select_pairs(None, count=4)] for _ in range(3)]
        assert runs[0] == runs[1] == runs[2]


class TestWordChoices:
    def test_choosing_the_plain_word_makes_avoidance_evidence(
        self, initialised, all_choices
    ):
        storage = Storage.open(initialised)
        assert calibrate(
            initialised, "--pairs", "3", "--choices", str(all_choices), "-n", "0"
        ) == EXIT_OK

        chosen = [e for e in storage.evidence() if e.kind == "calibration_choice"]
        assert len(chosen) == 3

        profile = storage.load_profile()
        confirmed = profile.notes["avoid_confirmed_by_choice"]
        assert confirmed
        assert [e.meta["formal"] for e in chosen] == confirmed
        # Real evidence sits at the top of the list, ahead of the guesses.
        assert profile.vocabulary["avoid"][: len(confirmed)] == confirmed

    def test_a_choice_stores_no_writing_of_theirs(self, initialised, all_choices):
        """The words on screen are ours. There is nothing of theirs to keep."""
        storage = Storage.open(initialised)
        before = len(list((initialised / "samples").glob("*.txt")))
        calibrate(initialised, "--pairs", "2", "--choices", str(all_choices), "-n", "0")

        chosen = [e for e in storage.evidence() if e.kind == "calibration_choice"]
        assert all(e.text_ref is None for e in chosen)
        assert all(e.word_count == 0 for e in chosen)
        assert len(list((initialised / "samples").glob("*.txt"))) == before

    def test_choosing_the_formal_word_keeps_it_out_of_avoid(
        self, initialised, tmp_path
    ):
        pair = select_pairs(Storage.open(initialised).load_profile(), count=1)[0]
        path = tmp_path / "formal.json"
        path.write_text(json.dumps({pair.id: pair.formal}), encoding="utf-8")

        calibrate(initialised, "--pairs", "1", "--choices", str(path), "-n", "0")
        profile = Storage.open(initialised).load_profile()
        assert pair.formal not in profile.vocabulary["avoid"]
        assert pair.formal in profile.vocabulary["prefer"]
        assert profile.notes["avoid_confirmed_by_choice"] == []

    def test_neither_counts_as_avoiding_the_formal_word(self, initialised, tmp_path):
        pair = select_pairs(Storage.open(initialised).load_profile(), count=1)[0]
        path = tmp_path / "neither.json"
        path.write_text(json.dumps({pair.id: SKIP}), encoding="utf-8")

        calibrate(initialised, "--pairs", "1", "--choices", str(path), "-n", "0")
        profile = Storage.open(initialised).load_profile()
        assert pair.formal in profile.notes["avoid_confirmed_by_choice"]
        assert pair.formal not in profile.vocabulary["prefer"]

    def test_choices_survive_a_rebuild_from_another_command(
        self, initialised, all_choices
    ):
        """The profile is a function of the log, choices included."""
        calibrate(initialised, "--pairs", "2", "--choices", str(all_choices), "-n", "0")
        confirmed = Storage.open(initialised).load_profile().notes[
            "avoid_confirmed_by_choice"
        ]
        main(
            ["--home", str(initialised), "analyse", "--save",
             str(FIXTURES / "formal_professional.txt")]
        )
        after = Storage.open(initialised).load_profile()
        assert after.notes["avoid_confirmed_by_choice"] == confirmed

    def test_the_notes_flag_still_admits_the_remaining_guesses(
        self, initialised, all_choices
    ):
        calibrate(initialised, "--pairs", "2", "--choices", str(all_choices), "-n", "0")
        profile = Storage.open(initialised).load_profile()
        assert profile.notes["avoid_inferred_from_absence"] is True
        assert len(profile.notes["avoid_confirmed_by_choice"]) == 2

    def test_a_nonsense_choice_is_refused_rather_than_guessed_at(
        self, initialised, tmp_path, capsys
    ):
        pair = select_pairs(Storage.open(initialised).load_profile(), count=1)[0]
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({pair.id: "banana"}), encoding="utf-8")
        assert calibrate(
            initialised, "--pairs", "1", "--choices", str(path), "-n", "0"
        ) == EXIT_ERROR
        assert "banana" in capsys.readouterr().out

    def test_pairs_zero_offers_none(self, initialised, all_choices):
        calibrate(initialised, "--pairs", "0", "--choices", str(all_choices), "-n", "0")
        storage = Storage.open(initialised)
        assert not [e for e in storage.evidence() if e.kind == "calibration_choice"]

    def test_verdicts_read_back_out_of_the_log(self, initialised, all_choices):
        calibrate(initialised, "--pairs", "3", "--choices", str(all_choices), "-n", "0")
        records = Storage.open(initialised).evidence()
        verdicts = verdicts_from_evidence(records)
        assert len(verdicts) == 3
        assert all(v.chosen == v.plain for v in verdicts)
        assert all(v.avoids_formal for v in verdicts)
        assert len(answered_pair_ids(records)) == 3

    def test_the_same_choices_give_the_same_profile(self, tmp_path, all_choices):
        onboarding = tmp_path / "onboarding.json"
        onboarding.write_text(json.dumps(ANSWERS), encoding="utf-8")
        vocabularies = []
        for name in ("a", "b"):
            home = tmp_path / name
            home.mkdir()
            main(
                ["--home", str(home), "init", "--answers", str(onboarding),
                 "--sample", str(FIXTURES / "casual_direct.txt")]
            )
            calibrate(home, "--pairs", "4", "--choices", str(all_choices), "-n", "0")
            vocabularies.append(Storage.open(home).load_profile().vocabulary)
        assert vocabularies[0] == vocabularies[1]

    def test_asking_for_nothing_says_so(self, initialised, capsys):
        assert calibrate(initialised, "-n", "0", "--pairs", "0") == EXIT_OK
        assert "Nothing to ask" in capsys.readouterr().out
