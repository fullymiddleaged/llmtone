"""Metrics on small, hand-counted strings, where the right answer is obvious."""

from __future__ import annotations

import pytest

from llmtone.analysis import analyse
from llmtone.analysis.punctuation import band, punctuation_metrics
from llmtone.analysis.syntax import syntax_metrics
from llmtone.analysis.text import (
    basic_metrics,
    mtld,
    split_paragraphs,
    split_sentences,
    tokenise,
)


class TestTokenising:
    def test_counts_hyphenated_and_contracted_words_once(self):
        assert tokenise("It's a well-known problem.") == [
            "it's", "a", "well-known", "problem"
        ]

    def test_normalises_curly_apostrophes(self):
        assert tokenise("It’s fine") == tokenise("It's fine")

    def test_numbers_are_words(self):
        assert tokenise("we shipped 3 fixes") == ["we", "shipped", "3", "fixes"]


class TestSentenceSplitting:
    def test_splits_on_terminal_punctuation(self):
        assert len(split_sentences("One. Two! Three?")) == 3

    @pytest.mark.parametrize(
        "text",
        [
            "See e.g. the docs for more.",
            "Ask Dr. Weber about it.",
            "Contact J. Smith directly.",
        ],
    )
    def test_abbreviations_do_not_end_a_sentence(self, text):
        assert len(split_sentences(text)) == 1

    def test_paragraph_break_ends_a_sentence_without_punctuation(self):
        assert len(split_sentences("A heading\n\nSome body text.")) == 2

    def test_bullet_items_are_separate_sentences(self):
        text = "Do these:\n\n- first thing\n- second thing\n- third thing"
        # One lead-in plus three items, none of which are punctuated.
        assert len(split_sentences(text)) == 4

    def test_a_five_item_list_is_not_one_giant_sentence(self):
        text = "\n".join(f"- item number {i}" for i in range(5))
        assert basic_metrics(text).average_sentence_length < 5


class TestParagraphs:
    def test_blank_lines_separate_paragraphs(self):
        assert len(split_paragraphs("One.\n\nTwo.\n\n\nThree.")) == 3

    def test_single_newlines_do_not(self):
        assert len(split_paragraphs("One.\nStill one.")) == 1


class TestBasicMetrics:
    def test_counts(self):
        metrics = basic_metrics("One two three. Four five.")
        assert metrics.word_count == 5
        assert metrics.sentence_count == 2
        assert metrics.average_sentence_length == 2.5

    def test_variance_is_zero_for_even_sentences(self):
        assert basic_metrics("a b c. d e f. g h i.").sentence_length_variance == 0.0

    def test_empty_text_does_not_divide_by_zero(self):
        metrics = basic_metrics("")
        assert metrics.word_count == 0
        assert metrics.average_sentence_length == 0.0
        assert metrics.vocabulary_diversity == 0.0


class TestMTLD:
    def test_short_text_returns_zero(self):
        assert mtld(["a", "b", "c"]) == 0.0

    def test_repetitive_text_scores_lower_than_varied_text(self):
        repetitive = ["the", "cat", "the", "cat"] * 15
        varied = [f"word{i}" for i in range(60)]
        assert mtld(repetitive) < mtld(varied)

    def test_is_not_simply_length_dependent(self):
        """The reason MTLD is used instead of type-token ratio.

        Doubling a varied text leaves diversity roughly where it was; raw TTR
        would halve.
        """
        varied = [f"w{i}" for i in range(80)]
        assert mtld(varied + varied) > mtld(varied) * 0.5


class TestSyntax:
    def test_contractions_counted_but_possessives_are_not(self):
        metrics = syntax_metrics("It's Sarah's problem and we're on it.")
        assert metrics.contraction_count == 2

    def test_contraction_preference_is_a_ratio_not_a_rate(self):
        contracted = syntax_metrics("It's fine. We're fine. They're fine.")
        expanded = syntax_metrics("It is fine. We are fine. They are fine.")
        assert contracted.contraction_preference == 1.0
        assert expanded.contraction_preference == 0.0

    def test_pronoun_rates(self):
        metrics = syntax_metrics("I think you know what I mean.")
        assert metrics.first_person_count == 2
        assert metrics.second_person_count == 1

    def test_questions(self):
        assert syntax_metrics("Is it? Yes. Really?").question_count == 2

    def test_passive_approximation_fires_on_obvious_passives(self):
        assert syntax_metrics("The report was written by the team.").passive_count == 1

    def test_imperative_openers(self):
        assert syntax_metrics("Check the logs. Fix the build.").imperative_count == 2

    def test_imperatives_are_only_detected_sentence_initially(self):
        """Known limit: "Then fix it" is an instruction but does not count."""
        assert syntax_metrics("Then fix it.").imperative_count == 0

    def test_sentence_initial_conjunctions(self):
        metrics = syntax_metrics("It broke. But we fixed it. So we moved on.")
        assert metrics.initial_conjunction_count == 2


class TestPunctuation:
    def test_counts_each_mark(self):
        metrics = punctuation_metrics("Hi; this (really) works -- yes!")
        assert metrics.counts["semicolon"] == 1
        assert metrics.counts["parentheses"] == 1
        assert metrics.counts["exclamation"] == 1

    def test_double_hyphen_counts_as_an_em_dash_not_two_hyphens(self):
        metrics = punctuation_metrics("one -- two")
        assert metrics.counts["em_dash"] == 1
        assert metrics.counts["hyphen"] == 0

    def test_ellipsis_is_not_three_periods(self):
        metrics = punctuation_metrics("Well... maybe")
        assert metrics.counts["ellipsis"] == 1
        assert metrics.counts["period"] == 0

    def test_zero_count_is_never_not_rare(self):
        assert band("semicolon", 0.0, 0) == "never"

    def test_bands_are_per_mark(self):
        """20 commas per 1000 words is ordinary; 20 semicolons is a habit."""
        assert band("comma", 20.0, 20) == "rare"
        assert band("semicolon", 20.0, 20) == "frequent"


class TestVocabulary:
    def test_hedges_detected_as_words_and_phrases(self):
        vocab = analyse("It might work. Sort of. I suppose.").vocabulary
        assert vocab.hedge_rate > 0

    def test_kind_regards_is_not_counted_as_hedging(self):
        """"kind of" hedges; "kind regards" does not."""
        assert analyse("Kind regards, Sam").vocabulary.hedge_rate == 0.0

    def test_buzzwords_detected(self):
        vocab = analyse("We should leverage synergies going forward.").vocabulary
        assert vocab.buzzword_rate > 0

    def test_technical_shapes_detected_without_a_lexicon_entry(self):
        vocab = analyse("Edit the parse_config helper in loader.py first.").vocabulary
        assert "parse_config" in vocab.technical_terms
        assert "loader.py" in vocab.technical_terms

    def test_avoid_list_is_empty_for_short_text(self):
        """Absence means nothing in fifty words, so nothing is claimed."""
        assert analyse("A short note about nothing much.").vocabulary.avoid == []

    def test_avoid_list_appears_once_there_is_enough_text(self, ):
        text = ("We fixed the thing and moved on. " * 40)
        assert analyse(text).vocabulary.avoid != []


class TestAnalysisContract:
    def test_every_declared_feature_is_produced(self):
        from llmtone.analysis import FEATURE_NAMES

        assert set(analyse("Some ordinary text here.").features) == set(FEATURE_NAMES)

    def test_approximations_are_flagged_in_the_output(self):
        dump = analyse("The report was written.").to_dict()
        assert "passive_voice" in dump["approximate_metrics"]

    def test_analysis_holds_no_raw_text(self):
        """Nothing that leaves the analyser should carry the writing itself."""
        secret = "hunter2 is the password"
        dump = repr(analyse(f"{secret} and some other words here."))
        assert secret not in dump
