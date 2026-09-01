"""Tests for src/scorer.py. Owner: Elav (feature/scoring-core).

The assignment hands us this test suite: seven worked examples in the English
appendix and five in the Hebrew body.
"""

import pytest

from src.normalizer import normalize
from src.scorer import (
    INDEL_PENALTIES,
    SUBSTITUTION_PENALTIES,
    Variant,
    indel_penalty,
    score_exact,
    score_extra_char,
    score_ladder,
    score_missing_char,
    score_substitution,
    substitution_penalty,
)

ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789 "
SHAKESPEARE = normalize("To be or not to be, that is the question.")


class TestPenaltyTables:
    def test_transcribed_from_the_assignment(self):
        assert SUBSTITUTION_PENALTIES == (5, 4, 3, 2, 1)
        assert INDEL_PENALTIES == (10, 8, 6, 4, 2)

    @pytest.mark.parametrize(
        "position,expected", [(1, 5), (2, 4), (3, 3), (4, 2), (5, 1)]
    )
    def test_substitution_positions(self, position, expected):
        assert substitution_penalty(position) == expected

    @pytest.mark.parametrize(
        "position,expected", [(1, 10), (2, 8), (3, 6), (4, 4), (5, 2)]
    )
    def test_indel_positions(self, position, expected):
        assert indel_penalty(position) == expected

    @pytest.mark.parametrize("position", [5, 6, 10, 100, 3_450_000])
    def test_last_value_repeats_from_position_five(self, position):
        assert substitution_penalty(position) == 1
        assert indel_penalty(position) == 2

    @pytest.mark.parametrize("position", [0, -1])
    def test_rejects_non_positive_positions(self, position):
        """Positions are 1-based. Silently accepting 0 would corrupt scores."""
        with pytest.raises(ValueError):
            substitution_penalty(position)
        with pytest.raises(ValueError):
            indel_penalty(position)


class TestEnglishAppendixExamples:
    """All seven worked examples, against the assignment's own sentence."""

    @pytest.mark.parametrize(
        "query,expected",
        [("To be", 10), ("or Not", 12), ("be, that", 14)],
    )
    def test_exact_matches(self, query, expected):
        assert score_exact(len(normalize(query))) == expected

    @pytest.mark.parametrize(
        "query,position,expected",
        [("2o be", 1, 3), ("to pe", 4, 6)],
    )
    def test_substitutions(self, query, position, expected):
        assert score_substitution(len(normalize(query)), position) == expected

    def test_extra_character(self):
        """`or knot` -> delete the extra `k` at position 4 -> 2 x 6 - 4 = 8."""
        assert score_extra_char(len(normalize("or knot")), 4) == 8

    def test_missing_character(self):
        """`or nt` -> insert the missing `o` at position 5 -> 2 x 5 - 2 = 8.

        The inserted `o` earns no matching points, but all five typed
        characters still do — that is the asymmetry against `extra_char`.
        """
        assert score_missing_char(len(normalize("or nt")), 5) == 8


class TestHebrewBodyExamples:
    """The five worked examples from the Hebrew body.

    These call the score functions DIRECTLY and never go through normalize().
    The corpus is English-only, so normalization keeps only [a-z0-9 ] and would
    strip every Hebrew character, reducing these queries to spaces. The Hebrew
    examples verify the FORMULAS; the English ones exercise normalization.
    Mixing the two produces a failing test that looks like a scoring bug and is
    not one — hence the explicit lengths and positions below.
    """

    def test_exact(self):
        assert score_exact(11) == 22

    @pytest.mark.parametrize("position,expected", [(11, 19), (4, 18)])
    def test_substitutions(self, position, expected):
        assert score_substitution(11, position) == expected

    def test_extra_character(self):
        assert score_extra_char(12, 4) == 18

    def test_missing_character(self):
        assert score_missing_char(10, 3) == 14


class TestTheAsymmetry:
    """The single easiest thing in this project to get wrong."""

    def test_missing_keeps_all_matching_points_extra_does_not(self):
        length, position = 10, 5
        assert score_missing_char(length, position) == 2 * length - 2
        assert score_extra_char(length, position) == 2 * (length - 1) - 2

    def test_missing_always_beats_extra_at_the_same_position(self):
        for length in range(3, 20):
            for position in range(1, length + 1):
                assert score_missing_char(length, position) > score_extra_char(
                    length, position
                )


class TestScoreLadderStructure:
    QUERY = SHAKESPEARE[:12]  # 'to be or not'

    def _groups(self, query=None, alphabet=ALPHABET):
        return list(score_ladder(query if query is not None else self.QUERY, alphabet))

    def test_first_group_is_the_exact_query_alone(self):
        first = self._groups()[0]
        assert first == [Variant(text=self.QUERY, score=2 * len(self.QUERY))]

    def test_scores_are_strictly_descending_across_groups(self):
        scores = [group[0].score for group in self._groups()]
        assert scores == sorted(scores, reverse=True)
        assert len(scores) == len(set(scores))

    def test_every_variant_in_a_group_shares_its_score(self):
        for group in self._groups():
            assert len({variant.score for variant in group}) == 1

    def test_at_most_ten_tiers(self):
        assert len(self._groups()) <= 10

    def test_tier_scores_match_the_documented_ladder(self):
        length = len(self.QUERY)
        expected = [2 * length - delta for delta in (0, 2, 3, 4, 5, 6, 7, 8, 10, 12)]
        assert [group[0].score for group in self._groups()] == expected


class TestScoreLadderFilters:
    QUERY = "to be or not"

    def _variants(self, query=QUERY, alphabet=ALPHABET):
        return [v for group in score_ladder(query, alphabet) for v in group]

    def test_no_variant_is_yielded_twice(self):
        texts = [v.text for v in self._variants()]
        assert len(texts) == len(set(texts))

    def test_duplicate_insertions_keep_the_best_score(self):
        """For `aa`, inserting `a` at 1, 2 or 3 all yield `aaa`.

        Position 3 is the cheapest (penalty 6), so `aaa` must appear once, at
        that score, not at position 1's penalty of 10.
        """
        variants = {v.text: v.score for v in self._variants("aaaa", "a")}
        assert variants["aaaaa"] == score_missing_char(4, 5)

    def test_no_double_spaces(self):
        assert all("  " not in v.text for v in self._variants())

    def test_no_empty_variants(self):
        assert all(v.text for v in self._variants())

    def test_no_non_positive_scores(self):
        assert all(v.score > 0 for v in self._variants())

    def test_empty_query_yields_nothing(self):
        assert list(score_ladder("", ALPHABET)) == []


class TestShortQueries:
    """A consequence of the penalty scale: below 3 characters, only exact
    matches can score above zero. Documented so it is not mistaken for a bug.
    """

    @pytest.mark.parametrize("query", ["a", "ab"])
    def test_only_the_exact_tier_survives(self, query):
        groups = list(score_ladder(query, ALPHABET))
        assert groups == [[Variant(text=query, score=2 * len(query))]]

    def test_three_characters_admits_edited_tiers(self):
        assert len(list(score_ladder("abc", ALPHABET))) > 1


class TestLaziness:
    def test_stopping_after_the_first_tier_builds_almost_nothing(self):
        """Callers stop at 5 results, usually in tier 1. Generating all ~1500
        variants up front would waste that.
        """
        ladder = score_ladder(SHAKESPEARE, ALPHABET)
        first = next(ladder)
        assert len(first) == 1
        ladder.close()

    def test_is_a_generator_not_a_list(self):
        assert not isinstance(score_ladder("abc", ALPHABET), list)


class TestAlphabetIsHonoured:
    def test_only_alphabet_characters_are_introduced(self):
        alphabet = "xyz "
        query = "abc"
        introduced = set()
        for group in score_ladder(query, alphabet):
            for variant in group:
                introduced |= set(variant.text) - set(query)
        assert introduced <= set(alphabet)

    def test_a_wider_alphabet_produces_more_variants(self):
        narrow = sum(len(g) for g in score_ladder("abc", "ab "))
        wide = sum(len(g) for g in score_ladder("abc", ALPHABET))
        assert wide > narrow
