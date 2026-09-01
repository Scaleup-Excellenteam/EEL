"""Tests for the typo cache and its first-check hook in the engine."""

import pytest

from src import autocomplete as autocomplete_module
from src.autocomplete import AutoCompleteEngine
from src.models import SentenceData
from src.scorer import Variant
from src.typo_cache import TypoCache


class FakeCorpus:
    alphabet = "abc "

    def __init__(self, sentences: dict[int, SentenceData]) -> None:
        self._sentences = sentences

    def __getitem__(self, line_id: int) -> SentenceData:
        return self._sentences[line_id]


class FakeIndex:
    def __init__(self, streams: dict[str, list[int]]) -> None:
        self._streams = streams
        self.calls: list[str] = []

    def find_lines_containing(self, pattern: str):
        self.calls.append(pattern)
        return iter(self._streams.get(pattern, []))


def sentence_with(normalized: str) -> SentenceData:
    return SentenceData(
        original_sentence=normalized,
        normalized_sentence=normalized,
        source_text="demo.txt",
        offset=1,
    )


def stub_ladder(monkeypatch: pytest.MonkeyPatch, query: str, ladder):
    monkeypatch.setattr(autocomplete_module, "normalize", lambda text: query)

    def fake_score_ladder(actual_query: str, alphabet: str):
        assert actual_query == query
        yield from ladder

    monkeypatch.setattr(autocomplete_module, "score_ladder", fake_score_ladder)


def test_record_stores_correct_word_and_frequency_one():
    cache = TypoCache()

    cache.record("arrray", "array")

    assert cache.lookup("arrray") == ("array", 1)


def test_record_increments_frequency_for_the_same_typo():
    cache = TypoCache()

    cache.record("hte", "the")
    cache.record("hte", "the")
    cache.record("hte", "the")

    assert cache.lookup("hte") == ("the", 3)


def test_unknown_typo_lookup_returns_none():
    assert TypoCache().lookup("unknwon") is None


def test_does_not_record_empty_or_identical_strings():
    cache = TypoCache()

    cache.record("", "the")
    cache.record("the", "")
    cache.record("the", "the")

    assert cache.lookup("") is None
    assert cache.lookup("the") is None


def test_record_match_stores_only_the_changed_word():
    cache = TypoCache()

    cache.record_match("numpy arrray", "numpy array")

    assert cache.lookup("arrray") == ("array", 1)
    assert cache.lookup("numpy arrray") is None
    assert cache.lookup("numpy") is None


def test_record_match_stores_full_strings_when_word_counts_differ():
    cache = TypoCache()

    cache.record_match("thisis", "this is")

    assert cache.lookup("thisis") == ("this is", 1)


def test_preferred_texts_replaces_a_known_typo_token():
    cache = TypoCache()
    cache.record("arrray", "array")

    assert cache.preferred_texts("numpy arrray") == ("numpy array",)


def test_prioritize_is_a_no_op_when_the_cache_is_empty():
    group = [Variant(text="left", score=8), Variant(text="right", score=8)]

    assert TypoCache().prioritize("query", group) is group


def test_prioritize_moves_the_known_correction_first():
    cache = TypoCache()
    cache.record("qury", "query")
    group = [
        Variant(text="xury", score=7),
        Variant(text="query", score=7),
        Variant(text="zury", score=7),
    ]

    ordered = cache.prioritize("qury", group)

    assert [variant.text for variant in ordered] == ["query", "xury", "zury"]


def test_engine_records_a_typo_when_only_a_corrected_variant_matches(
    monkeypatch: pytest.MonkeyPatch,
):
    index = FakeIndex({"numpy arrray": [], "numpy array": [0]})
    engine = AutoCompleteEngine(
        FakeCorpus({0: sentence_with("use numpy array here")}), index
    )
    stub_ladder(
        monkeypatch,
        "numpy arrray",
        [
            [Variant(text="numpy arrray", score=24)],
            [Variant(text="numpy array", score=21)],
        ],
    )

    engine.get_best_k_completions("numpy arrray")

    assert engine.typo_cache.lookup("arrray") == ("array", 1)


def test_engine_does_not_record_an_exact_match(monkeypatch: pytest.MonkeyPatch):
    index = FakeIndex({"numpy array": [0]})
    engine = AutoCompleteEngine(
        FakeCorpus({0: sentence_with("numpy array")}), index
    )
    stub_ladder(
        monkeypatch,
        "numpy array",
        [[Variant(text="numpy array", score=22)]],
    )

    engine.get_best_k_completions("numpy array")

    assert engine.typo_cache.lookup("numpy") is None
    assert engine.typo_cache.lookup("array") is None
    assert engine.typo_cache.lookup("numpy array") is None


def test_second_search_tries_the_cached_correction_first(
    monkeypatch: pytest.MonkeyPatch,
):
    index = FakeIndex(
        {"numpy arrray": [], "numpy xrray": [], "numpy array": [0]}
    )
    engine = AutoCompleteEngine(
        FakeCorpus({0: sentence_with("use numpy array here")}), index
    )
    stub_ladder(
        monkeypatch,
        "numpy arrray",
        [
            [Variant(text="numpy arrray", score=24)],
            [
                Variant(text="numpy xrray", score=21),
                Variant(text="numpy array", score=21),
            ],
        ],
    )

    engine.get_best_k_completions("numpy arrray")
    index.calls.clear()
    engine.get_best_k_completions("numpy arrray")

    substitution_calls = [call for call in index.calls if call != "numpy arrray"]
    assert substitution_calls[0] == "numpy array"
