"""Brute-force reference implementation. Owner: Elav (feature/scoring-core).

TEST-ONLY. The running program never imports this.

Its whole purpose is to be obviously correct rather than fast, so that the
score-ladder optimisation can be *verified* instead of merely believed. It
computes what the answer must be by definition: for every sentence, try every
edit at every position and keep the best score.

Write for obviousness. If you find yourself optimising this, you have defeated
its purpose.

See specs/elav-scoring-core.md section 6.
"""

from src.scorer import (
    score_exact,
    score_extra_char,
    score_missing_char,
    score_substitution,
)


def best_score(query: str, normalized_sentence: str, alphabet: str) -> int | None:
    """The best score `query` can earn against one sentence, or None if no match.

    Directly transcribed from the assignment's rules, with no cleverness:
    a match is the query as a substring, or the query as a substring after
    exactly one substitution, one deletion, or one insertion.

    Variants containing a double space need no special handling here — a
    normalized sentence never contains one, so the `in` test rejects them by
    itself. That is one fewer rule than the fast path needs, which is the point.
    """
    length = len(query)
    if length == 0:
        return None

    best: int | None = None

    def consider(score: int) -> None:
        nonlocal best
        if score > 0 and (best is None or score > best):
            best = score

    # No edit.
    if query in normalized_sentence:
        consider(score_exact(length))

    # One character substituted.
    for position in range(1, length + 1):
        prefix, suffix = query[: position - 1], query[position:]
        replaced = query[position - 1]
        for character in alphabet:
            if character != replaced and prefix + character + suffix in normalized_sentence:
                consider(score_substitution(length, position))
                break  # the score does not depend on which character it was

    # One character too many in the query — delete it.
    for position in range(1, length + 1):
        candidate = query[: position - 1] + query[position:]
        if candidate and candidate in normalized_sentence:
            consider(score_extra_char(length, position))

    # One character missing from the query — insert it.
    for position in range(1, length + 2):
        prefix, suffix = query[: position - 1], query[position - 1 :]
        for character in alphabet:
            if prefix + character + suffix in normalized_sentence:
                consider(score_missing_char(length, position))
                break

    return best


def best_k(
    query: str, normalized_sentences: list[str], alphabet: str, k: int = 5
) -> list[tuple[int, int]]:
    """The correct top-`k` answer, as (score, line_id) pairs.

    `normalized_sentences` must be indexed by line ID, which means the caller
    has already applied the loader's ordering contract. Ties therefore break on
    ascending line ID, which is what the contract makes equivalent to
    alphabetical order.
    """
    hits: list[tuple[int, int]] = []
    for line_id, sentence in enumerate(normalized_sentences):
        score = best_score(query, sentence, alphabet)
        if score is not None:
            hits.append((score, line_id))

    hits.sort(key=lambda hit: (-hit[0], hit[1]))
    return hits[:k]
