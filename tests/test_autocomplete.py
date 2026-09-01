"""Tests for Monjed's online search orchestration."""

from collections.abc import Iterable

import pytest

from src import autocomplete as autocomplete_module
from src.autocomplete import AutoCompleteEngine
from src.models import AutoCompleteData, SentenceData
from src.scorer import Variant


class FakeCorpus:
    alphabet = "abc "

    def __init__(self, sentences: dict[int, SentenceData]) -> None:
        self._sentences = sentences

    def __getitem__(self, line_id: int) -> SentenceData:
        return self._sentences[line_id]


class FakeIndex:
    def __init__(self, streams: dict[str, Iterable[int]]) -> None:
        self._streams = streams
        self.calls: list[str] = []

    def find_lines_containing(self, pattern: str):
        self.calls.append(pattern)
        return iter(self._streams.get(pattern, []))


def sentence(line_id: int) -> SentenceData:
    return SentenceData(
        original_sentence=f"Sentence {line_id}",
        normalized_sentence=f"sentence {line_id}",
        source_text=f"file{line_id}.txt",
        offset=line_id + 1,
    )


def corpus(size: int = 10) -> FakeCorpus:
    return FakeCorpus({line_id: sentence(line_id) for line_id in range(size)})


def tier(score: int, *texts: str) -> list[Variant]:
    return [Variant(text=text, score=score) for text in texts]


def stub_scoring(monkeypatch: pytest.MonkeyPatch, normalized: str, ladder):
    calls: dict[str, list] = {"normalize": [], "score_ladder": []}

    def fake_normalize(text: str) -> str:
        calls["normalize"].append(text)
        return normalized

    def fake_score_ladder(query: str, alphabet: str):
        calls["score_ladder"].append((query, alphabet))
        yield from ladder

    monkeypatch.setattr(autocomplete_module, "normalize", fake_normalize)
    monkeypatch.setattr(autocomplete_module, "score_ladder", fake_score_ladder)
    return calls


def result_ids(results: list[AutoCompleteData]) -> list[int]:
    return [result.offset - 1 for result in results]


def test_collects_normal_results(monkeypatch: pytest.MonkeyPatch):
    calls = stub_scoring(monkeypatch, "query", [tier(10, "query")])
    index = FakeIndex({"query": [0, 2]})

    results = AutoCompleteEngine(corpus(), index).get_best_k_completions("Query")

    assert calls == {
        "normalize": ["Query"],
        "score_ladder": [("query", FakeCorpus.alphabet)],
    }
    assert index.calls == ["query"]
    assert results == [
        AutoCompleteData("Sentence 0", "file0.txt", 1, 10),
        AutoCompleteData("Sentence 2", "file2.txt", 3, 10),
    ]


def test_merges_multiple_sorted_streams_within_one_tier(monkeypatch: pytest.MonkeyPatch):
    stub_scoring(monkeypatch, "query", [tier(20, "left", "right")])
    index = FakeIndex({"left": [0, 3], "right": [1, 2]})

    results = AutoCompleteEngine(corpus(), index).get_best_k_completions("query")

    assert index.calls == ["left", "right"]
    assert result_ids(results) == [0, 1, 2, 3]


def test_deduplicates_line_ids(monkeypatch: pytest.MonkeyPatch):
    stub_scoring(monkeypatch, "query", [tier(20, "left", "right")])
    index = FakeIndex({"left": [0, 1], "right": [1, 2]})

    results = AutoCompleteEngine(corpus(), index).get_best_k_completions("query")

    assert result_ids(results) == [0, 1, 2]


def test_line_keeps_highest_score_from_first_tier(monkeypatch: pytest.MonkeyPatch):
    stub_scoring(
        monkeypatch,
        "query",
        [
            tier(30, "high"),
            tier(12, "low"),
        ],
    )
    index = FakeIndex({"high": [1], "low": [1, 2]})

    results = AutoCompleteEngine(corpus(), index).get_best_k_completions("query")

    assert result_ids(results) == [1, 2]
    assert [result.score for result in results] == [30, 12]


def test_stops_early_after_k_results(monkeypatch: pytest.MonkeyPatch):
    stub_scoring(
        monkeypatch,
        "query",
        [
            tier(30, "enough"),
            tier(20, "must-not-run"),
        ],
    )
    index = FakeIndex({"enough": [0, 1, 2], "must-not-run": [3]})

    results = AutoCompleteEngine(corpus(), index).get_best_k_completions("query", k=2)

    assert result_ids(results) == [0, 1]
    assert index.calls == ["enough"]


def test_does_not_consume_past_needed_results(monkeypatch: pytest.MonkeyPatch):
    class RaisesIfOverread:
        def __iter__(self):
            yield 0
            yield 1
            raise AssertionError("stream consumed after k results were collected")

    stub_scoring(monkeypatch, "query", [tier(30, "enough")])
    index = FakeIndex({"enough": RaisesIfOverread()})

    results = AutoCompleteEngine(corpus(), index).get_best_k_completions("query", k=2)

    assert result_ids(results) == [0, 1]


def test_returns_fewer_than_k_results(monkeypatch: pytest.MonkeyPatch):
    stub_scoring(monkeypatch, "query", [tier(10, "a"), tier(8, "b")])
    index = FakeIndex({"a": [0], "b": [2]})

    results = AutoCompleteEngine(corpus(), index).get_best_k_completions("query", k=5)

    assert result_ids(results) == [0, 2]


def test_returns_empty_list_when_no_results(monkeypatch: pytest.MonkeyPatch):
    stub_scoring(monkeypatch, "query", [tier(10, "missing")])
    index = FakeIndex({"missing": []})

    results = AutoCompleteEngine(corpus(), index).get_best_k_completions("query")

    assert results == []
    assert index.calls == ["missing"]


def test_empty_query_does_not_search(monkeypatch: pytest.MonkeyPatch):
    def fail_score_ladder(query: str, alphabet: str):
        raise AssertionError("score_ladder should not be called")
        yield

    monkeypatch.setattr(autocomplete_module, "normalize", lambda text: "")
    monkeypatch.setattr(autocomplete_module, "score_ladder", fail_score_ladder)
    index = FakeIndex({})

    results = AutoCompleteEngine(corpus(), index).get_best_k_completions("   ")

    assert results == []
    assert index.calls == []
