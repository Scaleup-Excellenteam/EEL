"""Inverted index. Owner: Qusai (feature/offline-index).

M0 STUB — signatures frozen, implementation pending.

This module holds the single primitive the entire project reduces to:
"given an exact string, find the lines containing it — fast."

See specs/qusai-offline-index.md section 5.
"""

from collections.abc import Iterator
from pathlib import Path

from src.loader import Corpus


class InvertedIndex:
    """Word-level inverted index: word -> sorted list of line IDs.

    Sizing: ~20 M word occurrences as array('i') is roughly 80 MB. A character
    4-gram index would need ~480 MB and build far more slowly; it is the escape
    hatch for short queries, not the plan.

    Build hint: accumulate into per-word Python lists, then freeze into ONE flat
    array('i') plus a dict[str, tuple[int, int]] of (start, end) slices.
    Per-word array objects carry too much per-object overhead at ~500 K distinct
    words.
    """

    @classmethod
    def build(cls, corpus: Corpus) -> "InvertedIndex":
        raise NotImplementedError("Qusai — feature/offline-index")

    def find_lines_containing(self, pattern: str) -> Iterator[int]:
        """Yield line IDs whose normalized text contains `pattern`.

        TWO LOAD-BEARING PROPERTIES:

          - MUST yield in ASCENDING line-ID order. This is what makes the
            alphabetical tie-break correct.
          - MUST be LAZY. The caller stops early, usually after 5 results. A
            version that builds and returns a list is correct but slow, and
            speed is half the grade.

        `pattern` is already normalized.

        Strategy (specs/qusai-offline-index.md 5.2):
            1. Split `pattern` on spaces.
            2. Keep only STRICTLY INTERIOR tokens — those with a space on both
               sides within the pattern. Edge tokens may be fragments: in
               `or no` the trailing `no` may be part of `not` and the leading
               `or` may be part of `for`.
            3. Of those, pick the token with the SMALLEST posting list.
            4. Walk that posting list in ascending order, lazily.
            5. Verify each candidate with `pattern in corpus.normalized(line_id)`.
            6. Yield the line ID if it verifies.

        The index narrows candidates; verification decides matches. That is what
        makes this exact rather than approximate.

        Patterns with no strictly interior token take the fallback in section
        5.4. Note that the assignment's own worked example (`this is`) hits that
        fallback, so it is the common path for short queries, not an edge case.
        """
        raise NotImplementedError("Qusai — feature/offline-index")

    def save(self, path: Path) -> None:
        """Persist the index. Behind a flag — see SPEC.md 7.4."""
        raise NotImplementedError("Qusai — feature/offline-index")

    @classmethod
    def load(cls, path: Path) -> "InvertedIndex":
        raise NotImplementedError("Qusai — feature/offline-index")
