"""Additional tests for src/typo_cache.py: the private `_edits` helper with
more than one differing word, and the interaction between a whole-query
correction and a token-level one inside `preferred_texts` — neither is
exercised by the existing typo cache tests, which check each in isolation."""

from src.typo_cache import TypoCache, _edits


def test_edits_records_each_differing_word_independently():
    pairs = _edits("fx jmps dog", "fox jumps dog")

    assert pairs == (("fx", "fox"), ("jmps", "jumps"))


def test_preferred_texts_puts_whole_query_correction_before_token_level_ones():
    cache = TypoCache()
    cache.record("abc xyz", "correct phrase")
    cache.record("xyz", "xyz2")

    preferred = cache.preferred_texts("abc xyz")

    assert preferred == ("correct phrase", "abc xyz2")
