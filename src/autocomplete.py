"""Search orchestration. Owner: Monjed (feature/online-search).

M0 STUB — signatures frozen, implementation pending.

See specs/monjed-online-search.md section 3.
"""

from src.index import InvertedIndex
from src.loader import Corpus
from src.models import AutoCompleteData

DEFAULT_K = 5


class AutoCompleteEngine:
    """Assembles the scorer's ladder and the index's lookups into an answer."""

    def __init__(self, corpus: Corpus, index: InvertedIndex) -> None:
        raise NotImplementedError("Monjed — feature/online-search")

    def get_best_k_completions(
        self, prefix: str, k: int = DEFAULT_K
    ) -> list[AutoCompleteData]:
        """Return the best `k` completions for `prefix`, best score first.

        The name and the `prefix` parameter are mandated by the assignment. Keep
        them exactly, misleading as `prefix` is — the match is a substring
        ANYWHERE in the sentence, not a prefix.

        Algorithm:

            normalized = normalize(prefix)
            results, seen = [], set()

            for group in score_ladder(normalized, corpus.alphabet):
                # each variant yields its OWN ascending stream — MERGE them
                streams = [index.find_lines_containing(v.text) for v in group]
                for line_id in heapq.merge(*streams):
                    if line_id in seen:
                        continue
                    seen.add(line_id)
                    results.append(...)      # score comes from the group
                    if len(results) == k:
                        return results
            return results

        THREE THINGS TO GET RIGHT:

        1. MERGE within a tier, never sort. A tier holds several variants (tier
           2L-4 holds three edit kinds), each with its own ascending stream. The
           streams are individually sorted but not jointly sorted, so combine
           with heapq.merge. Concatenating and sorting would drain every stream
           and destroy early termination.

        2. Dedup by LINE ID, not by text, and a line keeps its FIRST score.
           Walking tiers in descending order means the first sighting of a line
           is at its best achievable score. The same sentence in two different
           files is two distinct lines and may legitimately take two slots.

        3. The tie-break is FREE. Ascending line IDs already are alphabetical
           order, by the loader's ordering contract. Appending in arrival order
           is correct. If you ever feel the need to sort, that contract has been
           violated upstream — raise it with Qusai rather than papering over it
           here.

        No edit distance is ever computed. If you find yourself writing one, the
        design has been misread.
        """
        raise NotImplementedError("Monjed — feature/online-search")
