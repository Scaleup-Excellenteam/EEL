"""Score formulas and the score ladder. Owner: Elav (feature/scoring-core).

M0 STUB — signatures frozen, implementations pending.

The penalty tables and `Variant` ARE implemented, because they are contract data
transcribed straight from the assignment rather than algorithm. Monjed consumes
`Variant`, so it must be concrete at M0.

See specs/elav-scoring-core.md sections 4 and 5.
"""

from collections.abc import Iterator
from dataclasses import dataclass

# Transcribed from the assignment's penalty table. The last value repeats for
# every position from 5 onward.
SUBSTITUTION_PENALTIES: tuple[int, ...] = (5, 4, 3, 2, 1)
INDEL_PENALTIES: tuple[int, ...] = (10, 8, 6, 4, 2)


@dataclass(frozen=True)
class Variant:
    """One guess at what the user meant, plus the score that guess earns.

    `text` is an already-corrected query, to be searched as an EXACT substring.
    `score` is known at construction time, before the corpus is consulted,
    because the score depends only on the query length and on which edit was
    applied where — never on which sentence matched.
    """

    text: str
    score: int


def substitution_penalty(position: int) -> int:
    """Penalty for substituting the character at 1-based `position`."""
    raise NotImplementedError("Elav — feature/scoring-core")


def indel_penalty(position: int) -> int:
    """Penalty for inserting or deleting at 1-based `position`."""
    raise NotImplementedError("Elav — feature/scoring-core")


def score_exact(length: int) -> int:
    """Exact substring: all `length` characters match, no penalty. 2L."""
    raise NotImplementedError("Elav — feature/scoring-core")


def score_substitution(length: int, position: int) -> int:
    """One character substituted: 2(L-1) - substitution_penalty(position).

    The substituted character earns no matching points.
    """
    raise NotImplementedError("Elav — feature/scoring-core")


def score_extra_char(length: int, position: int) -> int:
    """Query has an EXTRA character to delete: 2(L-1) - indel_penalty(position).

    `position` is the 1-based index in the original query. The extra character
    costs a matching point AS WELL AS the penalty, because it is not present in
    the sentence.
    """
    raise NotImplementedError("Elav — feature/scoring-core")


def score_missing_char(length: int, position: int) -> int:
    """Query is MISSING a character to insert: 2L - indel_penalty(position).

    Note the asymmetry against `score_extra_char`: here EVERY character the
    user typed does appear in the sentence, so all L of them count as matching.
    Only the inserted character earns nothing, and it costs no matching point
    because it was never typed.

    `position` is the 1-based index the inserted character OCCUPIES IN THE
    RESULT. The trap is an off-by-one — using the index of the character you
    insert after, rather than the index the new character lands on. The
    assignment's `or nt` example inserts at position 5 for penalty 2 and scores
    8; taking the preceding `n` at position 4 would apply penalty 4 and score 6.
    """
    raise NotImplementedError("Elav — feature/scoring-core")


def score_ladder(query: str, alphabet: str) -> Iterator[list[Variant]]:
    """Yield groups of variants in STRICTLY DESCENDING score order.

    This is what turns fuzzy matching into a sequence of exact substring
    searches, and it is why no edit distance is ever computed in this project.

    All variants in a yielded group share one score. There are exactly ten
    possible score tiers:

        2L      exact match
        2L-2    missing char at position >=5
        2L-3    substitution at position >=5
        2L-4    missing char at 4  | substitution at 4 | extra char at >=5
        2L-5    substitution at 3
        2L-6    missing char at 3  | substitution at 2 | extra char at 4
        2L-7    substitution at 1
        2L-8    missing char at 2  | extra char at 3
        2L-10   missing char at 1  | extra char at 2
        2L-12   extra char at 1

    Args:
        query: MUST already be normalized.
        alphabet: the characters observed in the corpus, from `Corpus.alphabet`.
            Never hardcode a-z — a wrong alphabet means missed matches. This is
            a three-way dependency: Qusai derives it, Monjed passes it, Elav
            consumes it.

    Four filters must be applied (specs/elav-scoring-core.md section 5):
        1. Global dedup, keeping the first (therefore highest-scoring)
           occurrence. Different edits can produce identical strings.
        2. Drop variants containing a double space — normalized corpus lines
           never contain one, so such a variant can never match.
        3. Drop empty variants — an empty string is contained in every line.
        4. Drop non-positive scores — they mean zero characters actually
           matched.
    """
    raise NotImplementedError("Elav — feature/scoring-core")
