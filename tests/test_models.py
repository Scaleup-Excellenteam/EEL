"""Tests for the frozen shared models.

M0 tests only what M0 implements: the models and the penalty tables. Everything
else is a stub, and its tests belong to whoever owns it.
"""

import dataclasses

import pytest

from src.models import AutoCompleteData, SentenceData
from src.scorer import INDEL_PENALTIES, SUBSTITUTION_PENALTIES, Variant


def _result(sentence: str, source: str = "example.txt", offset: int = 1, score: int = 14):
    return AutoCompleteData(
        completed_sentence=sentence, source_text=source, offset=offset, score=score
    )


class TestAutoCompleteDataShape:
    """The assignment mandates exactly four fields. Guard against drift."""

    def test_has_exactly_the_four_mandated_fields(self):
        names = [f.name for f in dataclasses.fields(AutoCompleteData)]
        assert names == ["completed_sentence", "source_text", "offset", "score"]

    def test_is_frozen(self):
        result = _result("Alpha: this is a demo.")
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.score = 99  # type: ignore[misc]


class TestSentenceDataShape:
    def test_field_names(self):
        names = [f.name for f in dataclasses.fields(SentenceData)]
        assert names == [
            "original_sentence",
            "normalized_sentence",
            "source_text",
            "offset",
        ]


class TestStr:
    def test_matches_the_assignment_sample_line(self):
        """The assignment's sample prints:

            1. Alpha: this is a demo. (example.txt:1, score=14)

        __str__ produces everything after the rank; the CLI prepends `1. `.
        """
        result = _result("Alpha: this is a demo.")
        assert str(result) == "Alpha: this is a demo. (example.txt:1, score=14)"

    def test_preserves_original_punctuation_and_casing(self):
        result = _result("To be or not to be, that is the question.", score=28)
        assert "To be or not to be, that is the question." in str(result)


class TestSortKey:
    def test_score_descending_beats_alphabetical(self):
        low = _result("aaa", score=10)
        high = _result("zzz", score=20)
        assert sorted([low, high], key=AutoCompleteData.sort_key) == [high, low]

    def test_equal_scores_sort_alphabetically(self):
        """The assignment: equal scores sort alphabetically."""
        names = ["Omega", "Alpha", "Delta", "Beta", "Gamma"]
        results = [_result(f"{n}: this is a demo.", offset=i) for i, n in enumerate(names)]
        ordered = [
            r.completed_sentence.split(":")[0]
            for r in sorted(results, key=AutoCompleteData.sort_key)
        ]
        assert ordered == ["Alpha", "Beta", "Delta", "Gamma", "Omega"]

    def test_casefold_avoids_the_ascii_case_artifact(self):
        """Raw ASCII sorting puts "Zebra" before "apple". Ours must not."""
        zebra = _result("Zebra", score=10)
        apple = _result("apple", score=10)
        ordered = sorted([zebra, apple], key=AutoCompleteData.sort_key)
        assert [r.completed_sentence for r in ordered] == ["apple", "Zebra"]

    def test_order_is_total_for_identical_sentences_in_different_files(self):
        """Same text in two files must still order deterministically."""
        a = _result("same text", source="a.txt", offset=5)
        b = _result("same text", source="b.txt", offset=1)
        assert sorted([b, a], key=AutoCompleteData.sort_key) == [a, b]

    def test_agrees_with_the_loader_ordering_contract(self):
        """sort_key minus the score MUST equal the loader's line-ID key.

        The loader assigns line IDs by
        (original_sentence.casefold(), source_text, offset). If these two ever
        diverge, ascending line IDs stop being alphabetical order and early
        termination silently returns mis-ordered results.
        """
        result = _result("Alpha: this is a demo.", source="example.txt", offset=3, score=14)
        loader_key = (
            result.completed_sentence.casefold(),
            result.source_text,
            result.offset,
        )
        assert result.sort_key() == (-result.score, *loader_key)


class TestPenaltyTables:
    """Transcribed from the assignment. A typo here corrupts every score."""

    def test_substitution_table(self):
        assert SUBSTITUTION_PENALTIES == (5, 4, 3, 2, 1)

    def test_indel_table(self):
        assert INDEL_PENALTIES == (10, 8, 6, 4, 2)


class TestVariant:
    def test_carries_text_and_precomputed_score(self):
        variant = Variant(text="to be", score=6)
        assert (variant.text, variant.score) == ("to be", 6)

    def test_is_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            Variant(text="to be", score=6).score = 7  # type: ignore[misc]
