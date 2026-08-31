"""Shared data models. Frozen at M0 — see SPEC.md section 5.

This is the only module all three developers depend on. Changing anything here
requires agreement between Elav, Qusai and Monjed.

These models are fully implemented rather than stubbed, because they ARE the
contract: everyone else builds against their exact shape.
"""

from dataclasses import dataclass

from src.normalizer import normalize


@dataclass(frozen=True)
class SentenceData:
    """One sentence from the corpus.

    Produced by the loader (Qusai), consumed by the engine (Monjed).

    `original_sentence` is preserved byte-for-byte because the assignment
    requires output in the source's original form, punctuation included.
    Matching happens on `normalized_sentence`; display uses
    `original_sentence`.
    """

    original_sentence: str
    normalized_sentence: str
    source_text: str
    offset: int


@dataclass(frozen=True)
class AutoCompleteData:
    """One autocomplete result.

    EXACTLY these four fields — never add one. The assignment's stub ends with
    `# methods that you need to define by yourself`: it invites methods, not
    extra fields. `sort_key` and `__str__` below are the whole extension, and
    both are computable from the four fields alone.
    """

    completed_sentence: str
    source_text: str
    offset: int
    score: int

    def sort_key(self) -> tuple[int, str, str, int]:
        """Ordering key: score descending, then the tie-break of SPEC.md 7.2.

        The alphabetical part sorts on the NORMALIZED sentence, not the raw one.
        That matters, and the first version got it wrong:

        Sorting on the raw line lets invisible characters decide the order,
        because control chars < tab < space < punctuation < digits < letters in
        ASCII. 40% of the real corpus (964,432 of 2,391,950 lines) starts with
        whitespace, and countless lines start with '>>>', '*', '#' or a digit.
        Since the engine returns results in ascending line-ID order and stops at
        the 5th hit, this was not a cosmetic ordering nit — alphabetically
        earlier sentences were silently dropped out of the result set entirely.
        Six equal-scoring matches where only the first was unindented returned
        the other five and omitted the alphabetically first one.

        Normalizing first makes the key say what the sentence actually says.
        `source_text` and `offset` then make the order total, so output is
        deterministic when the same sentence appears in more than one file.

        The loader assigns line IDs in ascending
        `(normalized_sentence, source_text, offset)` order — this key minus the
        score. `normalize(completed_sentence)` reproduces the loader's
        `normalized_sentence` exactly, because the loader computes it from the
        same original line. The two MUST stay in agreement, or ascending line
        IDs stop being alphabetical order and early termination silently returns
        the wrong five results.
        """
        return (
            -self.score,
            normalize(self.completed_sentence),
            self.source_text,
            self.offset,
        )

    def __str__(self) -> str:
        """Display form, per the assignment's sample output.

        The CLI prepends the rank, producing e.g.
        `1. Alpha: this is a demo. (example.txt:1, score=14)`
        """
        return (
            f"{self.completed_sentence} "
            f"({self.source_text}:{self.offset}, score={self.score})"
        )
