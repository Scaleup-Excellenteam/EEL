import heapq

from src.index import InvertedIndex
from src.loader import Corpus
from src.models import AutoCompleteData
from src.normalizer import normalize
from src.scorer import score_ladder
from src.typo_cache import TypoCache

DEFAULT_K = 5


class AutoCompleteEngine:
    """Assembles the scorer's ladder and the index's lookups into an answer."""

    def __init__(self, corpus: Corpus, index: InvertedIndex) -> None:
        self.corpus = corpus
        self.index = index
        self.typo_cache = TypoCache()

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
        matched_exactly = False
        recorded_typo = False

        for group in score_ladder(normalized, self.corpus.alphabet):
            if not group:
                continue

            group = self.typo_cache.prioritize(normalized, group)
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

                if not recorded_typo:
                    haystack = sentence.normalized_sentence
                    if normalized in haystack:
                        matched_exactly = True
                    elif not matched_exactly:
                        for variant in group:
                            if (
                                variant.text != normalized
                                and variant.text in haystack
                            ):
                                self.typo_cache.record_match(
                                    normalized, variant.text
                                )
                                recorded_typo = True
                                break

                if len(results) == k:
                    return results

        return results
