"""Tests for src/normalizer.py. Owner: Elav (feature/scoring-core)."""

import pytest

from src.normalizer import normalize

SHAKESPEARE = "To be or not to be, that is the question."


class TestAssignmentExamples:
    def test_the_reference_sentence(self):
        assert normalize(SHAKESPEARE) == "to be or not to be that is the question"

    @pytest.mark.parametrize(
        "raw,expected,length",
        [
            ("To be", "to be", 5),
            ("or Not", "or not", 6),
            ("be, that", "be that", 7),
            ("2o be", "2o be", 5),
            ("to pe", "to pe", 5),
            ("or knot", "or knot", 7),
            ("or nt", "or nt", 5),
        ],
    )
    def test_query_normalization_and_length(self, raw, expected, length):
        """The lengths matter as much as the text — they drive every score."""
        assert normalize(raw) == expected
        assert len(normalize(raw)) == length

    def test_the_three_equivalent_forms_from_the_assignment(self):
        """The assignment says these three must be treated as equivalent."""
        forms = ["be that", "be, that", "be              that"]
        assert len({normalize(form) for form in forms}) == 1


class TestPunctuationIsDeletedNotReplaced:
    def test_comma_leaves_seven_characters(self):
        """`be, that` scores 14, and 14 is 2 x 7. Eight would give 16."""
        assert len(normalize("be, that")) == 7

    def test_apostrophe_joins_the_word(self):
        """The case that really exposes delete-vs-replace."""
        assert normalize("don't") == "dont"

    def test_punctuation_between_spaces_does_not_leave_a_double_space(self):
        assert normalize("a , b") == "a b"

    def test_assorted_punctuation_is_removed(self):
        assert normalize("@!.,$#%^&*()") == ""


class TestWhitespace:
    def test_runs_collapse_to_one_space(self):
        assert normalize("a          b") == "a b"

    def test_tabs_and_newlines_become_spaces_not_deletions(self):
        """If punctuation were stripped first, this would give `bethat`."""
        assert normalize("be,\tthat") == "be that"
        assert normalize("be\nthat") == "be that"

    def test_ends_are_stripped(self):
        assert normalize("   padded   ") == "padded"

    def test_whitespace_only_input_is_empty(self):
        assert normalize("   \t\n  ") == ""


class TestDigitsSurvive:
    def test_digits_are_kept(self):
        """The assignment's `2o be` example substitutes a digit."""
        assert normalize("2o be") == "2o be"

    def test_mixed_alphanumeric(self):
        assert normalize("Python 3.8.4") == "python 384"


class TestProperties:
    @pytest.mark.parametrize(
        "text",
        [
            SHAKESPEARE,
            "",
            "   ",
            "a",
            "@!.,$",
            "Mixed CASE with   spaces, and punctuation!",
            "spam = 1  # and this is the second comment",
        ],
    )
    def test_idempotent(self, text):
        once = normalize(text)
        assert normalize(once) == once

    @pytest.mark.parametrize(
        "text", [SHAKESPEARE, "a , b", "  x  ", "@!.,$", "Python 3.8.4"]
    )
    def test_output_charset_is_only_lowercase_digits_and_single_spaces(self, text):
        result = normalize(text)
        assert all(c.islower() or c.isdigit() or c == " " for c in result)
        assert "  " not in result
        assert result == result.strip()

    def test_empty_input_is_empty_output(self):
        assert normalize("") == ""
