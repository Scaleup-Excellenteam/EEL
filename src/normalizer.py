"""Text normalization. Owner: Elav (feature/scoring-core).

Called by BOTH other tracks: the loader normalizes every corpus line during the
offline stage, the engine normalizes the user's query during the online stage.
Neither writes its own version. Two slightly different normalizers would put the
query and the corpus in different worlds and nothing would ever match.

See specs/elav-scoring-core.md section 3.
"""

import re

# Anything outside this set is punctuation and gets deleted. Note that digits
# are kept: they are not punctuation, and the assignment's `2o be` example
# substitutes one.
_NOT_KEPT = re.compile(r"[^a-z0-9 ]")

_WHITESPACE_RUN = re.compile(r"\s+")


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
    - PRESERVE digits.
    - Strip leading and trailing whitespace.

    The three passes below have to happen in this order:

    1. Whitespace first, so that tabs and newlines become spaces rather than
       being deleted as punctuation. `be,\\tthat` must reach `be that`, not
       `bethat`.
    2. Punctuation second.
    3. Whitespace again, because deleting punctuation can create a new double
       space that did not exist before: `a , b` becomes `a  b`.
    """
    collapsed = _WHITESPACE_RUN.sub(" ", text.lower())
    depunctuated = _NOT_KEPT.sub("", collapsed)
    return _WHITESPACE_RUN.sub(" ", depunctuated).strip()
