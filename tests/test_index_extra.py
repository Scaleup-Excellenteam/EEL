"""Additional tests for src/index.py, targeting the exact boundary of
`_MAX_CANDIDATE_WORDS` and the "no token could be priced" full-scan signal,
neither of which the existing index tests pin down precisely (they test far
past the cap, not at its edge)."""

from src.index import InvertedIndex, _MAX_CANDIDATE_WORDS, _bounded_prefix_scan


class FakeCorpus:
    def __init__(self, sentences):
        self.sentences = tuple(sentences)

    def __len__(self):
        return len(self.sentences)

    def normalized(self, line_id):
        return self.sentences[line_id]


def test_bounded_prefix_scan_returns_words_exactly_at_the_cap() -> None:
    words = tuple(sorted(f"a{i:04d}" for i in range(_MAX_CANDIDATE_WORDS)))

    result = _bounded_prefix_scan(words, "a")

    assert result == words
    assert len(result) == _MAX_CANDIDATE_WORDS


def test_bounded_prefix_scan_returns_none_one_word_past_the_cap() -> None:
    words = tuple(sorted(f"a{i:04d}" for i in range(_MAX_CANDIDATE_WORDS + 1)))

    result = _bounded_prefix_scan(words, "a")

    assert result is None


def test_cheapest_word_set_signals_full_scan_when_no_token_can_be_priced() -> None:
    """A two-word pattern where both tokens' candidate sets are too broad to
    price must return () (full scan) rather than None (provably unmatchable)
    or a wrongly-priced word set."""
    words_ending_in_ab = [f"w{i:04d}ab" for i in range(_MAX_CANDIDATE_WORDS + 100)]
    words_starting_with_cd = [f"cdw{i:04d}" for i in range(_MAX_CANDIDATE_WORDS + 100)]
    corpus = FakeCorpus(words_ending_in_ab + words_starting_with_cd)
    index = InvertedIndex.build(corpus)

    assert index._cheapest_word_set("ab cd") == ()
    # And the public method must still answer correctly via the full-scan path.
    assert list(index.find_lines_containing("ab cd")) == []
