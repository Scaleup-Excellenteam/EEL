"""Text normalization. Owner: Elav (feature/scoring-core).

M0 STUB — signature frozen, implementation pending.

Called by BOTH other tracks: the loader normalizes every corpus line during the
offline stage, the engine normalizes the user's query during the online stage.
Neither writes its own version. Two slightly different normalizers would put the
query and the corpus in different worlds and nothing would ever match.

See specs/elav-scoring-core.md section 3.
"""


def normalize(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace, strip the ends.

    Rules (specs/elav-scoring-core.md section 3):

    - Lowercase everything.
    - DELETE punctuation — never replace it with a space. `be, that` must
      become `be that` (7 characters), because the assignment scores that
      query 14 and 14 is 2 x 7. The case that really exposes this is an
      apostrophe: `don't` must become `dont`, not `don t`.
    - Collapse any run of whitespace to a single space. Spaces COUNT as
      characters for scoring.
    - PRESERVE digits. They are not punctuation, and the assignment's `2o be`
      example substitutes a digit.
    - Strip leading and trailing whitespace.

    Keeping only `[a-z0-9 ]` after lowercasing is the simple, defensible rule
    for this corpus.
    """
    raise NotImplementedError("Elav — feature/scoring-core")
