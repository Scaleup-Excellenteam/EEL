"""Word-level inverted index for exact normalized substring lookup.

Original implementation: Qusai (feature/offline-index).
Candidate-selection rewrite: Elav, at the M1 integration merge — see the note
below. Qusai owns this module; this change needs his review.


WHY THE CANDIDATE SELECTION WAS REWRITTEN
-----------------------------------------
The first version only used *strictly interior* tokens — those with a space on
both sides inside the pattern — and fell back to scanning every line when there
were none. That fallback was sound but it was also, in practice, the main path:

    'python'              interior tokens: []                -> FULL SCAN
    'this is'             interior tokens: []                -> FULL SCAN
    'import numpy'        interior tokens: []                -> FULL SCAN
    'the interpreter'     interior tokens: []                -> FULL SCAN
    'import numpy as np'  interior tokens: ['numpy', 'as']   -> index

A token is strictly interior only with a space on *both* sides, so a one- or
two-word pattern has none at all and a three-word pattern has exactly one. Since
the engine walks the score ladder, one mistyped two-word query generated 909
variants and roughly 90% of them each scanned all 2,391,950 lines. Measured on
the real corpus: `numpy arrray` did not finish in four minutes.

The fix is to notice that interiority is not the only thing a space tells you.
Every token sits at a known word boundary, and each boundary case is soundly
indexable:

    space before AND after   ->  the token is a WHOLE word
    space before only        ->  the token is a word PREFIX
    space after only         ->  the token is a word SUFFIX
    neither (single token)    ->  the token is a word INFIX

Only the whole-word case was being used. Adding the other three means no pattern
ever needs a corpus scan, and — more importantly — a garbage variant is rejected
in microseconds, because a token like `arrray` prefixes no corpus word at all.

Note the earlier idea of "just use an edge token as a whole word" is UNSOUND and
is deliberately not what this does. The line `bathis isnt here` contains
`this is`, yet has no word `this`; treating an edge token as a whole word would
silently miss it. specs/qusai-offline-index.md section 5.4 recommended exactly
that and was wrong.
"""

import heapq
import os
import pickle
import re
from array import array
from bisect import bisect_left
from pathlib import Path
from typing import Iterator

from src.loader import Corpus

# A candidate word set wider than this is treated as too broad to be worth
# pricing; some other token in the pattern will almost always be narrower.
_MAX_CANDIDATE_WORDS = 512

# Bumped whenever the on-disk snapshot layout changes, so `load` can refuse a
# file written by an incompatible version instead of misreading it.
_SNAPSHOT_FORMAT_VERSION = 1


class InvertedIndex:
    """Find normalized corpus lines containing exact substring patterns."""

    def __init__(
        self,
        corpus: Corpus,
        postings: array,
        word_ranges: dict[str, tuple[int, int]],
        words_sorted: tuple[str, ...],
        reversed_words_sorted: tuple[str, ...],
    ) -> None:
        self._corpus = corpus
        self._postings = postings
        self._word_ranges = word_ranges
        # Sorted distinct vocabulary, for prefix lookup by bisect.
        self._words_sorted = words_sorted
        # The same words reversed and re-sorted, so a suffix lookup is a prefix
        # lookup on reversed strings.
        self._reversed_words_sorted = reversed_words_sorted
        # All words in one string, space-delimited, for infix lookup at C speed.
        # A word never contains a space, so the delimiters cannot be crossed.
        self._word_blob = " " + " ".join(words_sorted) + " " if words_sorted else " "

    @property
    def corpus(self) -> Corpus:
        """The corpus this index was built over.

        Public so a caller that only has an `InvertedIndex` loaded from a
        snapshot (see `load` below) can still construct an `AutoCompleteEngine`
        without having to load or thread the corpus through separately.
        """
        return self._corpus

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

        words_sorted = tuple(sorted(word_ranges))
        reversed_words_sorted = tuple(sorted(word[::-1] for word in words_sorted))

        return cls(corpus, postings, word_ranges, words_sorted, reversed_words_sorted)

    # -- candidate word lookup, one method per boundary case ------------------

    # Each returns () when NO corpus word can satisfy the token — which makes the
    # whole pattern unmatchable — and None when the set was too broad to be worth
    # pricing. Keeping those two cases distinct matters: the first is a proof of
    # no match, the second is merely "ask a different token".

    def _whole(self, token: str) -> tuple[str, ...] | None:
        return (token,) if token in self._word_ranges else ()

    def _with_prefix(self, token: str) -> tuple[str, ...] | None:
        return _bounded_prefix_scan(self._words_sorted, token)

    def _with_suffix(self, token: str) -> tuple[str, ...] | None:
        reversed_matches = _bounded_prefix_scan(
            self._reversed_words_sorted, token[::-1]
        )
        if reversed_matches is None:
            return None
        return tuple(word[::-1] for word in reversed_matches)

    def _containing(self, token: str) -> tuple[str, ...] | None:
        """Words containing `token` anywhere, found by scanning the word blob.

        `str.find` runs at C speed over a few megabytes, which beats a Python
        loop over the vocabulary by two orders of magnitude.
        """
        found: list[str] = []
        blob = self._word_blob
        position = blob.find(token)
        while position != -1:
            start = blob.rfind(" ", 0, position) + 1
            end = blob.find(" ", position)
            found.append(blob[start:end])
            if len(found) > _MAX_CANDIDATE_WORDS:
                return None  # too broad to price; another token will be narrower
            position = blob.find(token, end)
        return tuple(found)

    def _candidate_words(self, pattern: str) -> Iterator[tuple[str, ...] | None]:
        """One candidate word set per token, by its boundary case."""
        tokens = pattern.split(" ")
        # Empty strings appear at the ends when the pattern has a leading or
        # trailing space, which is exactly the signal that the neighbouring
        # token sits at a word boundary.
        last = len(tokens) - 1

        for position, token in enumerate(tokens):
            if not token:
                continue
            space_before = position > 0
            space_after = position < last
            if space_before and space_after:
                yield self._whole(token)
            elif space_before:
                yield self._with_prefix(token)
            elif space_after:
                yield self._with_suffix(token)
            else:
                yield self._containing(token)

    def _cheapest_word_set(self, pattern: str) -> tuple[str, ...] | None:
        """The candidate word set with the fewest total postings.

        Returns None when the pattern provably cannot match anything, and () when
        no token could be priced and the caller must fall back to a full scan.
        """
        cheapest: tuple[str, ...] = ()
        cheapest_cost = -1

        for words in self._candidate_words(pattern):
            if words is None:
                continue  # too broad to price; try the next token
            if not words:
                return None  # no corpus word satisfies this token: no match

            cost = 0
            for word in words:
                start, end = self._word_ranges[word]
                cost += end - start
                if cheapest_cost != -1 and cost >= cheapest_cost:
                    break  # already worse than the incumbent; stop pricing
            else:
                if cheapest_cost == -1 or cost < cheapest_cost:
                    cheapest, cheapest_cost = words, cost

        return cheapest

    def _line_ids(self, words: tuple[str, ...]) -> Iterator[int]:
        """Line IDs for `words`, ascending and deduplicated, lazily."""
        if len(words) == 1:
            start, end = self._word_ranges[words[0]]
            yield from (self._postings[index] for index in range(start, end))
            return

        streams = []
        for word in words:
            start, end = self._word_ranges[word]
            streams.append(self._postings[index] for index in range(start, end))

        previous = -1
        for line_id in heapq.merge(*streams):
            if line_id != previous:
                previous = line_id
                yield line_id

    def find_lines_containing(self, pattern: str) -> Iterator[int]:
        """Yield verified matches lazily in ascending line-ID order.

        Both properties are load-bearing. Ascending order is what makes the
        alphabetical tie-break free, because the loader assigns line IDs in that
        order. Laziness is what lets the caller stop at the fifth result.

        The index only narrows the candidates; the `in` test below is what
        decides a match. That is what keeps this exact rather than approximate.
        """
        if not pattern:
            return

        tokens = [token for token in pattern.split(" ") if token]
        if not tokens:
            # A pattern of nothing but spaces. Unreachable from the score ladder
            # (it filters double spaces and non-positive scores), but a full scan
            # keeps the contract honest rather than silently returning nothing.
            candidates: Iterator[int] = iter(range(len(self._corpus)))
        else:
            words = self._cheapest_word_set(pattern)
            if words is None:
                return  # no corpus word can satisfy some token
            candidates = self._line_ids(words) if words else iter(range(len(self._corpus)))

        normalized = self._corpus.normalized
        for line_id in candidates:
            if pattern in normalized(line_id):
                yield line_id

    def save(self, path: Path) -> None:
        """Persist this index and its corpus to `path` in one file.

        This is the offline half of ZDT's filesystem hand-off (see
        `src/snapshot.py`): the online side never touches the corpus root or
        rebuilds the index, it only reads whatever file this writes.

        Written atomically — to a temp file in the same directory, then
        renamed into place — so a reader polling `path` never observes a
        partially written file. `os.replace` is a single rename() syscall on
        POSIX, which cannot interleave with a concurrent open() of `path`.
        """
        path = Path(path)
        payload = {
            "format_version": _SNAPSHOT_FORMAT_VERSION,
            "corpus": self._corpus.to_snapshot(),
            "postings": self._postings,
            "word_ranges": self._word_ranges,
            "words_sorted": self._words_sorted,
            "reversed_words_sorted": self._reversed_words_sorted,
        }
        temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with temp_path.open("wb") as file:
            pickle.dump(payload, file, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(temp_path, path)

    @classmethod
    def load(cls, path: Path) -> "InvertedIndex":
        """Load an index and its corpus from a file written by `save`."""
        with Path(path).open("rb") as file:
            payload = pickle.load(file)

        format_version = payload.get("format_version")
        if format_version != _SNAPSHOT_FORMAT_VERSION:
            raise ValueError(
                f"unsupported snapshot format version {format_version!r} "
                f"(expected {_SNAPSHOT_FORMAT_VERSION!r})"
            )

        corpus = Corpus.from_snapshot(payload["corpus"])
        return cls(
            corpus,
            payload["postings"],
            payload["word_ranges"],
            payload["words_sorted"],
            payload["reversed_words_sorted"],
        )


def _bounded_prefix_scan(
    sorted_words: tuple[str, ...], prefix: str
) -> tuple[str, ...] | None:
    """Words in `sorted_words` starting with `prefix`.

    Returns () when there are none — which proves the pattern unmatchable — and
    None when there are too many to be worth pricing, in which case some other
    token in the pattern will be narrower. A pattern whose every token is this
    broad falls back to a scan rather than to a wrong answer.
    """
    start = bisect_left(sorted_words, prefix)
    found: list[str] = []
    for index in range(start, len(sorted_words)):
        word = sorted_words[index]
        if not word.startswith(prefix):
            break
        found.append(word)
        if len(found) > _MAX_CANDIDATE_WORDS:
            return None
    return tuple(found)


def _strictly_interior_tokens(pattern: str) -> tuple[str, ...]:
    """Return tokens with a literal space on both sides in ``pattern``.

    Retained because it names a real and useful concept — these are the tokens
    guaranteed to be whole corpus words. It is no longer the only thing candidate
    selection uses; see the module docstring.
    """
    return tuple(re.findall(r"(?<= )[^ ]+(?= )", pattern))
