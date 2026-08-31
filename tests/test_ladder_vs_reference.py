"""Proof that the score ladder equals brute force. Owner: Elav.

This is the test that makes the whole design trustworthy. `score_ladder` is an
optimisation: it claims that walking tiers top-down and doing exact substring
searches produces exactly what an obviously-correct brute-force scan produces.
That claim is checked here against `tests/reference.py`.

The ladder walk below is a deliberately naive stand-in for the real engine — it
scans every sentence for each variant instead of using an index. That keeps this
test about the LADDER, with no dependency on Qusai's index or Monjed's engine.
"""

import random
import string

import pytest

from src.normalizer import normalize
from src.scorer import score_ladder
from tests.reference import best_k, best_score

ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789 "

CORPUS_RAW = [
    "To be or not to be, that is the question.",
    "A cup of tea, please.",
    "Not to be confused with the other one.",
    "Top performance is the goal.",
    "Alpha: this is a demo.",
    "Beta: this is a demo.",
    "Delta: this is a demo.",
    "Gamma: this is a demo.",
    "Omega: this is a demo.",
    "The quick brown fox jumps over the lazy dog.",
    "Spam, spam, spam and eggs.",
    "aaaa bbbb cccc",
]

# Line IDs must follow the loader's ordering contract, so that ties break on
# ascending line ID exactly as they will in production.
CORPUS = [normalize(raw) for raw in sorted(CORPUS_RAW, key=str.casefold)]


def ladder_best_k(query: str, sentences: list[str], alphabet: str, k: int = 5):
    """Walk the ladder the way the real engine will, but without an index."""
    results: list[tuple[int, int]] = []
    seen: set[int] = set()

    for group in score_ladder(query, alphabet):
        tier_hits = {
            line_id
            for variant in group
            for line_id, sentence in enumerate(sentences)
            if variant.text in sentence
        }
        for line_id in sorted(tier_hits):
            if line_id in seen:
                continue
            seen.add(line_id)
            results.append((group[0].score, line_id))
            if len(results) == k:
                return results

    return results


class TestAgreementOnAssignmentExamples:
    @pytest.mark.parametrize(
        "query,expected",
        [
            ("To be", 10),
            ("or Not", 12),
            ("be, that", 14),
            ("2o be", 3),
            ("to pe", 6),
            ("or knot", 8),
            ("or nt", 8),
        ],
    )
    def test_reference_reproduces_the_appendix(self, query, expected):
        """The oracle itself must match the assignment before we trust it."""
        sentence = normalize("To be or not to be, that is the question.")
        assert best_score(normalize(query), sentence, ALPHABET) == expected

    def test_not_be_is_not_a_match(self):
        """The appendix marks this N/A: no substring within one edit."""
        sentence = normalize("To be or not to be, that is the question.")
        assert best_score(normalize("not be"), sentence, ALPHABET) is None

    @pytest.mark.parametrize(
        "query",
        ["To be", "or Not", "be, that", "2o be", "to pe", "or knot", "or nt", "not be"],
    )
    def test_ladder_agrees_with_reference(self, query):
        normalized = normalize(query)
        assert ladder_best_k(normalized, CORPUS, ALPHABET) == best_k(
            normalized, CORPUS, ALPHABET
        )


class TestAgreementOnTheSampleScenario:
    def test_this_is_reproduces_the_assignment_sample(self):
        """`this is` must return the five demo lines, alphabetically, at 14."""
        results = ladder_best_k(normalize("this is"), CORPUS, ALPHABET)
        assert len(results) == 5
        assert {score for score, _ in results} == {14}

        sentences = sorted(CORPUS_RAW, key=str.casefold)
        names = [sentences[line_id].split(":")[0] for _, line_id in results]
        assert names == ["Alpha", "Beta", "Delta", "Gamma", "Omega"]

    def test_and_agrees_with_reference(self):
        normalized = normalize("this is")
        assert ladder_best_k(normalized, CORPUS, ALPHABET) == best_k(
            normalized, CORPUS, ALPHABET
        )


class TestAgreementUnderMutation:
    """Generated queries, seeded so failures are reproducible."""

    @staticmethod
    def _mutations(rng: random.Random, text: str) -> list[str]:
        if not text:
            return []
        position = rng.randrange(len(text))
        letter = rng.choice(string.ascii_lowercase)
        return [
            text[:position] + letter + text[position + 1 :],  # substitution
            text[:position] + letter + text[position:],  # extra character
            text[:position] + text[position + 1 :],  # missing character
        ]

    def _queries(self, seed: int, count: int) -> list[str]:
        rng = random.Random(seed)
        queries: list[str] = []
        while len(queries) < count:
            sentence = rng.choice(CORPUS)
            start = rng.randrange(max(1, len(sentence) - 12))
            fragment = sentence[start : start + rng.randint(3, 12)]
            queries.append(fragment)
            queries.extend(self._mutations(rng, fragment))
        return queries[:count]

    @pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
    def test_ladder_matches_reference_on_generated_queries(self, seed):
        for query in self._queries(seed, 40):
            assert ladder_best_k(query, CORPUS, ALPHABET) == best_k(
                query, CORPUS, ALPHABET
            ), f"disagreement on {query!r} (seed {seed})"

    def test_two_edits_never_match(self):
        """The assignment allows one edit. Two must fall out of the result set."""
        # `this is demo` needs both an `a` and a space inserted.
        assert best_score(normalize("this is demo"), CORPUS[0], ALPHABET) is None
        assert all(
            best_score(normalize("this is demo"), sentence, ALPHABET) is None
            for sentence in CORPUS
        )


class TestOrderingContract:
    def test_ties_come_back_in_ascending_line_id_order(self):
        results = ladder_best_k(normalize("this is"), CORPUS, ALPHABET)
        line_ids = [line_id for _, line_id in results]
        assert line_ids == sorted(line_ids)

    def test_a_line_is_never_returned_twice(self):
        for query in ["to be", "this is", "the", "a demo"]:
            line_ids = [lid for _, lid in ladder_best_k(normalize(query), CORPUS, ALPHABET)]
            assert len(line_ids) == len(set(line_ids))

    def test_scores_are_non_increasing(self):
        for query in ["to pe", "this is", "or knot", "tha"]:
            scores = [s for s, _ in ladder_best_k(normalize(query), CORPUS, ALPHABET)]
            assert scores == sorted(scores, reverse=True)
