"""Corpus loading. Owner: Qusai (feature/offline-index).

M0 STUB — signatures frozen, implementation pending.

See specs/qusai-offline-index.md section 4.
"""

from collections.abc import Iterator
from pathlib import Path

from src.models import SentenceData


class Corpus:
    """Every sentence in the corpus, addressable by line ID.

    THE LINE-ID ORDERING CONTRACT — the highest-risk line in the project:

        Line IDs are assigned in ascending order of
        `(original_sentence.casefold(), source_text, offset)`

    This is the same key as `AutoCompleteData.sort_key` minus the score. Note it
    is the ORIGINAL sentence case-folded, not the normalized form.

    Every posting list, sorted by line ID, is then already in the required
    tie-break order. That makes the alphabetical tie-break free and makes the
    engine's lazy early termination legal — it can stop at the 5th hit instead
    of collecting every hit and sorting.

    Breaking this contract produces no exception and no failing assertion, just
    quietly mis-ordered output. It must be asserted by an explicit test.

    Also required:
      - EXCLUDE lines whose normalized form is empty (blank lines,
        punctuation-only lines). They cannot match any non-empty query.
      - Preserve `original_sentence` byte-for-byte.
      - 3.45 M dataclass instances is memory-hostile. Store columnar internally
        and build a `SentenceData` on demand in `__getitem__`.
    """

    alphabet: str
    """Every distinct character observed after normalization.

    Derived from the actual corpus — never hardcoded. The scorer generates
    substitution and insertion variants from this, so a wrong alphabet means
    missed matches.
    """

    @classmethod
    def load(cls, root: Path) -> "Corpus":
        """Walk `root` recursively, reading every .txt file line by line.

        Files sit at varying depths — up to 3 levels in the real corpus. Never
        assume a flat layout.

        Encoding policy must be decided and documented; utf-8 with
        errors="replace" is the safe default for 1,504 files we did not author.
        """
        raise NotImplementedError("Qusai — feature/offline-index")

    def __len__(self) -> int:
        """Number of sentences, after empty-normalized lines are excluded."""
        raise NotImplementedError("Qusai — feature/offline-index")

    def __getitem__(self, line_id: int) -> SentenceData:
        raise NotImplementedError("Qusai — feature/offline-index")

    def normalized(self, line_id: int) -> str:
        """Fast path for verification — avoids building a `SentenceData`."""
        raise NotImplementedError("Qusai — feature/offline-index")

    def __iter__(self) -> Iterator[SentenceData]:
        raise NotImplementedError("Qusai — feature/offline-index")
