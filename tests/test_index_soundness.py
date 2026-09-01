"""Exhaustive soundness proof for InvertedIndex candidate selection.

Added by Elav at the M1 integration merge, alongside the candidate-selection
rewrite in src/index.py. Qusai owns that module; this file exists because the
rewrite trades a provably-sound full scan for four boundary-case lookups, and
that trade needs to be verified rather than argued.

`find_lines_containing` is only allowed to narrow candidates. It must return
EXACTLY the set of lines whose normalized text contains the pattern — never
fewer. Every test here compares it against brute force on generated data.
"""

import random
import string

import pytest

from src.index import InvertedIndex


class FakeCorpus:
    """Minimal corpus: what InvertedIndex.build actually consumes."""

    def __init__(self, sentences):
        self.sentences = tuple(sentences)

    def __len__(self):
        return len(self.sentences)

    def normalized(self, line_id):
        return self.sentences[line_id]


def brute_force(sentences, pattern):
    return [i for i, s in enumerate(sentences) if pattern in s]


def assert_sound(sentences, pattern):
    index = InvertedIndex.build(FakeCorpus(sentences))
    actual = list(index.find_lines_containing(pattern))
    expected = brute_force(sentences, pattern)
    assert actual == expected, (
        f"pattern {pattern!r}\n  expected {expected}\n  actual   {actual}\n"
        f"  missed   {sorted(set(expected) - set(actual))}\n"
        f"  spurious {sorted(set(actual) - set(expected))}"
    )
    assert actual == sorted(actual), f"not ascending for {pattern!r}"


class TestTheFourBoundaryCases:
    """One test per token classification, each with a case that would break a
    naive implementation."""

    SENTENCES = (
        "bathis isnt here",  # contains 'this is' but has NO word 'this'
        "this is fine",
        "the interpreter stack",
        "specifying the interpreter",
        "numpy array creation",
        "import numpy as np",
        "a b c d e",
    )

    @pytest.mark.parametrize(
        "pattern",
        [
            "this is",  # suffix + prefix, and the bathis trap
            " this is ",  # whole + whole
            " this is",  # whole + prefix
            "this is ",  # suffix + whole
            "numpy",  # infix, single token
            "umpy arr",  # suffix + prefix, both partial words
            " b c ",  # whole words, single characters
            "b c d",  # suffix + whole + prefix
            "a b c d e",  # every class at once
            "e",  # infix matching many words
            " a",  # prefix only
            "e ",  # suffix only
        ],
    )
    def test_matches_brute_force(self, pattern):
        assert_sound(self.SENTENCES, pattern)

    def test_the_unsound_shortcut_would_have_failed_here(self):
        """Guards the specific bug that using an edge token as a whole word causes.

        Line 0 contains 'this is' but its words are bathis/isnt/here. Treating
        the edge token 'this' as a whole word would look up postings for 'this',
        find only line 1, and silently miss line 0.
        """
        index = InvertedIndex.build(FakeCorpus(self.SENTENCES))
        assert list(index.find_lines_containing("this is")) == [0, 1]


class TestRandomisedDifferential:
    """Generated corpora and patterns, seeded so failures reproduce."""

    @staticmethod
    def _corpus(rng, n_lines, vocabulary):
        return tuple(
            " ".join(rng.choice(vocabulary) for _ in range(rng.randint(1, 8)))
            for _ in range(n_lines)
        )

    @staticmethod
    def _patterns(rng, sentences, count):
        """Patterns drawn from real substrings, plus deliberate near-misses.

        Real substrings exercise the found path; near-misses exercise the
        rejection path, which is where an unsound shortcut shows up as a wrong
        empty result rather than a crash.
        """
        patterns = []
        while len(patterns) < count:
            sentence = rng.choice(sentences)
            start = rng.randrange(len(sentence))
            end = min(len(sentence), start + rng.randint(1, 12))
            fragment = sentence[start:end]
            if not fragment:
                continue
            patterns.append(fragment)
            # one-character mutations, the shapes the score ladder generates
            position = rng.randrange(len(fragment))
            letter = rng.choice(string.ascii_lowercase + " ")
            patterns.append(fragment[:position] + letter + fragment[position + 1 :])
            patterns.append(fragment[:position] + letter + fragment[position:])
            patterns.append(fragment[:position] + fragment[position + 1 :])
        return [p for p in patterns[:count] if p and "  " not in p]

    @pytest.mark.parametrize("seed", range(8))
    def test_short_vocabulary(self, seed):
        """A tiny vocabulary maximises shared prefixes and suffixes, which is
        where prefix/suffix lookups are most likely to over- or under-match."""
        rng = random.Random(seed)
        vocabulary = ["a", "ab", "abc", "b", "ba", "bab", "c", "ca", "cab"]
        sentences = self._corpus(rng, 60, vocabulary)
        for pattern in self._patterns(rng, sentences, 150):
            assert_sound(sentences, pattern)

    @pytest.mark.parametrize("seed", range(8))
    def test_wordlike_vocabulary(self, seed):
        rng = random.Random(1000 + seed)
        vocabulary = [
            "import", "numpy", "array", "arrays", "as", "np", "the", "interpreter",
            "this", "is", "a", "demo", "bathis", "isnt", "stack", "python", "def",
            "main", "return", "1", "23", "x1y",
        ]
        sentences = self._corpus(rng, 80, vocabulary)
        for pattern in self._patterns(rng, sentences, 150):
            assert_sound(sentences, pattern)

    @pytest.mark.parametrize("seed", range(4))
    def test_words_that_embed_each_other(self, seed):
        """The hardest case for word-boundary reasoning: every word is a
        substring of another, so a pattern spanning a space can also occur
        entirely inside a single longer word."""
        rng = random.Random(2000 + seed)
        vocabulary = ["is", "this", "thisis", "bathisis", "isthis", "sis", "his", "athis"]
        sentences = self._corpus(rng, 50, vocabulary)
        for pattern in self._patterns(rng, sentences, 200):
            assert_sound(sentences, pattern)


class TestBreadthCapFallsBackRatherThanLying:
    """When every token is too broad to price, the result must still be correct.

    The cap exists for speed. If it ever caused a wrong answer it would be a
    correctness bug, so this drives a corpus where one letter prefixes far more
    words than the cap allows.
    """

    def test_very_broad_pattern_still_exact(self):
        sentences = tuple(f"a{index:04d} filler text" for index in range(1200))
        # 'a' prefixes all 1200 distinct words, well past _MAX_CANDIDATE_WORDS
        for pattern in ["a", " a", "a0", "a01", "filler", " filler ", "text"]:
            assert_sound(sentences, pattern)


class TestDegenerateInputs:
    SENTENCES = ("alpha beta", "gamma delta")

    @pytest.mark.parametrize("pattern", ["", " ", "  ", "   "])
    def test_space_only_and_empty_patterns_do_not_crash(self, pattern):
        index = InvertedIndex.build(FakeCorpus(self.SENTENCES))
        result = list(index.find_lines_containing(pattern))
        assert result == brute_force(self.SENTENCES, pattern) or pattern == ""

    def test_pattern_longer_than_any_line(self):
        assert_sound(self.SENTENCES, "alpha beta gamma delta epsilon zeta")

    def test_character_absent_from_the_corpus(self):
        assert_sound(self.SENTENCES, "zzz")

    def test_empty_corpus(self):
        index = InvertedIndex.build(FakeCorpus(()))
        assert list(index.find_lines_containing("anything")) == []


class TestLazinessSurvivedTheRewrite:
    def test_first_result_does_not_walk_the_corpus(self):
        class Tracking(FakeCorpus):
            def __init__(self, sentences):
                super().__init__(sentences)
                self.visited = []

            def normalized(self, line_id):
                self.visited.append(line_id)
                return self.sentences[line_id]

        corpus = Tracking(tuple(f"target line {i}" for i in range(500)))
        index = InvertedIndex.build(corpus)
        corpus.visited.clear()

        results = index.find_lines_containing("target line")
        assert corpus.visited == []  # nothing touched before the first next()
        assert next(results) == 0
        assert corpus.visited == [0]  # exactly one line touched
        results.close()
