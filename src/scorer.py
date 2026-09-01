"""Score formulas and the score ladder. Owner: Elav (feature/scoring-core).

See specs/elav-scoring-core.md sections 4 and 5.
"""

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass

# Transcribed from the assignment's penalty table. The last value repeats for
# every position from 5 onward.
SUBSTITUTION_PENALTIES: tuple[int, ...] = (5, 4, 3, 2, 1)
INDEL_PENALTIES: tuple[int, ...] = (10, 8, 6, 4, 2)

# Edit kinds, used to plan the ladder before any variant string is built.
_EXACT = "exact"
_MISSING = "missing"
_SUBSTITUTION = "substitution"
_EXTRA = "extra"


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


def _penalty(table: tuple[int, ...], position: int) -> int:
    if position < 1:
        raise ValueError(f"position is 1-based, got {position}")
    return table[min(position, len(table)) - 1]


def substitution_penalty(position: int) -> int:
    """Penalty for substituting the character at 1-based `position`."""
    return _penalty(SUBSTITUTION_PENALTIES, position)


def indel_penalty(position: int) -> int:
    """Penalty for inserting or deleting at 1-based `position`."""
    return _penalty(INDEL_PENALTIES, position)


def score_exact(length: int) -> int:
    """Exact substring: all `length` characters match, no penalty."""
    return 2 * length


def score_substitution(length: int, position: int) -> int:
    """One character substituted. The substituted character earns nothing."""
    return 2 * (length - 1) - substitution_penalty(position)


def score_extra_char(length: int, position: int) -> int:
    """Query has an EXTRA character, to be deleted.

    `position` is the 1-based index in the original query. The extra character
    costs a matching point AS WELL AS the penalty, because it is not present in
    the sentence.
    """
    return 2 * (length - 1) - indel_penalty(position)


def score_missing_char(length: int, position: int) -> int:
    """Query is MISSING a character, to be inserted.

    Note the asymmetry against `score_extra_char`: here EVERY character the
    user typed does appear in the sentence, so all `length` of them count as
    matching. Only the inserted character earns nothing, and it costs no
    matching point because it was never typed.

    `position` is the 1-based index the inserted character OCCUPIES IN THE
    RESULT. The trap is an off-by-one — using the index of the character you
    insert after, rather than the index the new character lands on. The
    assignment's `or nt` example inserts at position 5 for penalty 2 and scores
    8; taking the preceding `n` at position 4 would apply penalty 4 and score 6.
    """
    return 2 * length - indel_penalty(position)


def _plan(length: int) -> dict[int, list[tuple[str, int]]]:
    """Map each achievable score to the (edit kind, position) pairs that reach it.

    This is the ladder's skeleton, and it is built from `length` alone — no
    query content, no corpus, no strings. That is the whole insight: the score
    is knowable before anything is searched.

    Positions beyond 5 collapse onto position 5's penalty, so they share a tier
    with it rather than adding new ones. The result has at most ten entries.
    """
    plan: dict[int, list[tuple[str, int]]] = defaultdict(list)
    plan[score_exact(length)].append((_EXACT, 0))
    for position in range(1, length + 2):
        plan[score_missing_char(length, position)].append((_MISSING, position))
    for position in range(1, length + 1):
        plan[score_substitution(length, position)].append((_SUBSTITUTION, position))
        plan[score_extra_char(length, position)].append((_EXTRA, position))
    return plan


def _variants_for(
    query: str, alphabet: str, kind: str, position: int
) -> Iterator[str]:
    """Build the candidate strings for one (edit kind, position) pair."""
    if kind == _EXACT:
        yield query
        return

    index = position - 1

    if kind == _MISSING:
        prefix, suffix = query[:index], query[index:]
        for character in alphabet:
            yield prefix + character + suffix

    elif kind == _SUBSTITUTION:
        prefix, suffix = query[:index], query[position:]
        replaced = query[index]
        for character in alphabet:
            if character != replaced:
                yield prefix + character + suffix

    elif kind == _EXTRA:
        yield query[:index] + query[position:]

    else:  # pragma: no cover - guards against a typo in the plan
        raise ValueError(f"unknown edit kind {kind!r}")


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

    Variant strings are built tier by tier, only when that tier is reached, so a
    caller that stops after the exact-match tier has paid for one string rather
    than for all ~1500.

    Four filters, per specs/elav-scoring-core.md section 5:

    1. Global dedup keeping the first occurrence. Different edits can produce
       identical strings — for `aa`, inserting `a` at positions 1, 2 and 3 all
       yield `aaa`. Because tiers are walked in descending order, first-seen is
       automatically the best score that string can earn.
    2. Drop variants containing a double space. Normalized corpus lines never
       contain one, so such a variant can never match.
    3. Drop empty variants. An empty string is contained in every line, so it
       would match the entire corpus.
    4. Stop at the first non-positive tier. A score of zero or below means no
       character the user typed actually matched, and since tiers descend, every
       remaining tier is non-positive too.

    A consequence of filter 4 worth knowing: for a query of 1 or 2 characters
    every edited tier scores zero or less, so only exact matches are ever
    returned. That is the assignment's penalty scale doing its job, not a bug.
    """
    if not query:
        return

    plan = _plan(len(query))
    seen: set[str] = set()

    for score in sorted(plan, reverse=True):
        if score <= 0:
            return  # every remaining tier is lower, so also non-positive

        group: list[Variant] = []
        for kind, position in plan[score]:
            for text in _variants_for(query, alphabet, kind, position):
                if not text or "  " in text or text in seen:
                    continue
                seen.add(text)
                group.append(Variant(text=text, score=score))

        if group:
            yield group
