"""Word-level inverted index for exact normalized substring lookup."""

from array import array
from pathlib import Path
import re
from typing import Iterator

from src.loader import Corpus


class InvertedIndex:
    """Find normalized corpus lines containing exact substring patterns."""

    def __init__(
        self,
        corpus: Corpus,
        postings: array,
        word_ranges: dict[str, tuple[int, int]],
    ) -> None:
        self._corpus = corpus
        self._postings = postings
        self._word_ranges = word_ranges

    @classmethod
    def build(cls, corpus: Corpus) -> "InvertedIndex":
        postings_by_word: dict[str, list[int]] = {}
        for line_id in range(len(corpus)):
            words = set(corpus.normalized(line_id).split())
            for word in words:
                postings_by_word.setdefault(word, []).append(line_id)

        postings = array("i")
        word_ranges: dict[str, tuple[int, int]] = {}
        for word, line_ids in postings_by_word.items():
            start = len(postings)
            postings.extend(line_ids)
            word_ranges[word] = (start, len(postings))

        return cls(corpus, postings, word_ranges)

    def find_lines_containing(self, pattern: str) -> Iterator[int]:
        """Yield verified matches lazily in ascending line-ID order."""
        interior_tokens = _strictly_interior_tokens(pattern)
        if interior_tokens:
            ranges: list[tuple[int, int]] = []
            for token in interior_tokens:
                posting_range = self._word_ranges.get(token)
                if posting_range is None:
                    return
                ranges.append(posting_range)

            start, end = min(ranges, key=lambda bounds: bounds[1] - bounds[0])
            candidates = (self._postings[index] for index in range(start, end))
        else:
            candidates = iter(range(len(self._corpus)))

        for line_id in candidates:
            if pattern in self._corpus.normalized(line_id):
                yield line_id

    def save(self, path: Path) -> None:
        raise NotImplementedError("persistence is deferred until shared M0 integration")

    @classmethod
    def load(cls, path: Path) -> "InvertedIndex":
        raise NotImplementedError("persistence is deferred until shared M0 integration")


def _strictly_interior_tokens(pattern: str) -> tuple[str, ...]:
    """Return tokens with a literal space on both sides in ``pattern``."""
    return tuple(re.findall(r"(?<= )[^ ]+(?= )", pattern))
