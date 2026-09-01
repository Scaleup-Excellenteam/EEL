import heapq

from src.index import InvertedIndex
from src.loader import Corpus
from src.models import AutoCompleteData
from src.normalizer import normalize
from src.scorer import score_ladder

DEFAULT_K = 5


class AutoCompleteEngine:
    """Assembles the scorer's ladder and the index's lookups into an answer."""

    def __init__(self, corpus: Corpus, index: InvertedIndex) -> None:
        self.corpus = corpus
        self.index = index

    def get_best_k_completions(
        self, prefix: str, k: int = DEFAULT_K
    ) -> list[AutoCompleteData]:
        """Return the best `k` completions for `prefix`, best score first."""
        if k <= 0:
            return []

        normalized = normalize(prefix)
        if not normalized:
            return []

        results: list[AutoCompleteData] = []
        seen: set[int] = set()

        for group in score_ladder(normalized, self.corpus.alphabet):
            if not group:
                continue

            score = group[0].score
            streams = [
                self.index.find_lines_containing(variant.text) for variant in group
            ]

            for line_id in heapq.merge(*streams):
                if line_id in seen:
                    continue

                seen.add(line_id)
                sentence = self.corpus[line_id]
                results.append(
                    AutoCompleteData(
                        completed_sentence=sentence.original_sentence,
                        source_text=sentence.source_text,
                        offset=sentence.offset,
                        score=score,
                    )
                )

                if len(results) == k:
                    return results

        return results
