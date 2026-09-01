"""Additional tests for AutoCompleteEngine.get_best_k_completions: the k<=0
guard, which existing coverage of the class does not exercise."""

import pytest

from src import autocomplete as autocomplete_module
from src.autocomplete import AutoCompleteEngine


class ExplodingCorpus:
    alphabet = "abc "

    def __getitem__(self, line_id):
        raise AssertionError("corpus should not be consulted when k <= 0")


class ExplodingIndex:
    def find_lines_containing(self, pattern):
        raise AssertionError("index should not be searched when k <= 0")


def _refuses_to_normalize(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_normalize(text: str) -> str:
        raise AssertionError("normalize should not run when k <= 0")

    monkeypatch.setattr(autocomplete_module, "normalize", fail_normalize)


def test_k_zero_returns_empty_list_without_searching(monkeypatch: pytest.MonkeyPatch):
    _refuses_to_normalize(monkeypatch)
    engine = AutoCompleteEngine(ExplodingCorpus(), ExplodingIndex())

    results = engine.get_best_k_completions("this is", k=0)

    assert results == []


def test_negative_k_returns_empty_list_without_searching(monkeypatch: pytest.MonkeyPatch):
    _refuses_to_normalize(monkeypatch)
    engine = AutoCompleteEngine(ExplodingCorpus(), ExplodingIndex())

    results = engine.get_best_k_completions("this is", k=-5)

    assert results == []
