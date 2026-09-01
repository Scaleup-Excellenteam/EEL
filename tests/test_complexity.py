"""Performance-characteristic tests.

These don't pin down absolute timings (too flaky across machines); each one
grows the input by a known factor and asserts the running time grows by
nowhere near the square of that factor. A true O(n^2) implementation fails
these comfortably; a linear or near-linear one passes with room to spare.
Every threshold below is deliberately generous to avoid false failures on a
loaded or slow machine.
"""

import random
import time

from src.index import InvertedIndex
from src.normalizer import normalize
from src.scorer import score_ladder


class _FakeCorpus:
    def __init__(self, sentences):
        self.sentences = tuple(sentences)

    def __len__(self):
        return len(self.sentences)

    def normalized(self, line_id):
        return self.sentences[line_id]


def _best_of(fn, reps=3):
    best = None
    for _ in range(reps):
        start = time.perf_counter()
        fn()
        elapsed = time.perf_counter() - start
        best = elapsed if best is None else min(best, elapsed)
    return best


def test_normalize_time_scales_linearly_not_quadratically():
    small_text = ("word " * 2000) + ("don,t; me@il! 42 " * 2000)
    large_text = ("word " * 16000) + ("don,t; me@il! 42 " * 16000)  # 8x bigger

    small_time = _best_of(lambda: normalize(small_text))
    large_time = _best_of(lambda: normalize(large_text))

    # Linear predicts ~8x; quadratic would predict ~64x. Give it a wide berth.
    assert large_time < small_time * 25


def test_score_ladder_variant_count_scales_linearly_with_query_length():
    alphabet = "ab "

    def total_variants(length: int) -> int:
        query = "a" * length
        return sum(len(group) for group in score_ladder(query, alphabet))

    short_count = total_variants(10)
    long_count = total_variants(100)  # 10x longer query

    # The ladder builds O(length) variants per tier, never anything close to
    # exponential in the query length.
    assert long_count < short_count * 15


def test_index_build_time_scales_near_linearly_with_corpus_size():
    def make_corpus(n_lines: int) -> _FakeCorpus:
        rng = random.Random(42)
        vocabulary = [f"w{i}" for i in range(200)]
        return _FakeCorpus(
            " ".join(rng.choice(vocabulary) for _ in range(6)) for _ in range(n_lines)
        )

    small_corpus = make_corpus(1500)
    large_corpus = make_corpus(7500)  # 5x bigger

    small_time = _best_of(lambda: InvertedIndex.build(small_corpus))
    large_time = _best_of(lambda: InvertedIndex.build(large_corpus))

    # Linear predicts ~5x; quadratic would predict ~25x.
    assert large_time < small_time * 15


def test_indexed_lookup_of_a_rare_word_does_not_slow_down_as_corpus_grows():
    def make_corpus_with_one_rare_word(n_lines: int) -> _FakeCorpus:
        rng = random.Random(7)
        vocabulary = [f"w{i}" for i in range(200)]
        lines = [
            " ".join(rng.choice(vocabulary) for _ in range(6)) for _ in range(n_lines)
        ]
        lines[n_lines // 2] = "zzrareword " + lines[n_lines // 2]
        return _FakeCorpus(lines)

    small_index = InvertedIndex.build(make_corpus_with_one_rare_word(2000))
    large_index = InvertedIndex.build(make_corpus_with_one_rare_word(20000))  # 10x

    def lookup_many_times(index):
        for _ in range(2000):
            list(index.find_lines_containing("zzrareword"))

    small_time = _best_of(lambda: lookup_many_times(small_index))
    large_time = _best_of(lambda: lookup_many_times(large_index))

    # The whole point of an inverted index: a rare word's posting list doesn't
    # grow with the corpus, so lookup time for it shouldn't meaningfully
    # either. A linear (non-indexed) scan would instead show a ~10x slowdown.
    assert large_time < small_time * 4
