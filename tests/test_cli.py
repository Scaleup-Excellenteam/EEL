"""Tests for Monjed's CLI loop and entry-point wiring."""

from pathlib import Path

import main as main_module
from src import cli
from src.models import AutoCompleteData


class FakeEngine:
    def __init__(self, suggestions_by_query: dict[str, list[AutoCompleteData]]) -> None:
        self._suggestions_by_query = suggestions_by_query
        self.calls: list[str] = []

    def get_best_k_completions(self, prefix: str) -> list[AutoCompleteData]:
        self.calls.append(prefix)
        return self._suggestions_by_query.get(prefix, [])


def result(sentence: str, source: str = "example.txt", offset: int = 1, score: int = 14):
    return AutoCompleteData(
        completed_sentence=sentence,
        source_text=source,
        offset=offset,
        score=score,
    )


def run_cli(inputs: list[str], engine: FakeEngine) -> list[str]:
    remaining = iter(inputs)
    output: list[str] = []

    def read() -> str:
        return next(remaining)

    cli.run(engine, read=read, write=output.append)
    return output


def test_query_accumulates_between_enter_presses():
    engine = FakeEngine(
        {
            "this": [result("This works.", score=8)],
            "this is": [result("This is still one query.", score=14)],
        }
    )

    output = run_cli(["this", " is"], engine)

    assert engine.calls == ["this", "this is"]
    assert output == [
        cli.BANNER,
        "Here are 1 suggestions:",
        "1. This works. (example.txt:1, score=8)",
        "this",
        "Here are 1 suggestions:",
        "1. This is still one query. (example.txt:1, score=14)",
        "this is",
    ]


def test_hash_resets_accumulated_query():
    engine = FakeEngine(
        {
            "old": [result("Old suggestion.")],
            "new": [result("New suggestion.")],
        }
    )

    output = run_cli(["old", "#", "new"], engine)

    assert engine.calls == ["old", "new"]
    assert output == [
        cli.BANNER,
        "Here are 1 suggestions:",
        "1. Old suggestion. (example.txt:1, score=14)",
        "old",
        "Here are 1 suggestions:",
        "1. New suggestion. (example.txt:1, score=14)",
        "new",
    ]


def test_hash_inside_entered_text_resets_and_keeps_text_after_last_hash():
    engine = FakeEngine({"fresh": [result("Fresh start.")]})

    output = run_cli(["stale#fresh"], engine)

    assert engine.calls == ["fresh"]
    assert output == [
        cli.BANNER,
        "Here are 1 suggestions:",
        "1. Fresh start. (example.txt:1, score=14)",
        "fresh",
    ]


def test_empty_and_whitespace_only_input_do_not_search():
    engine = FakeEngine({})

    output = run_cli(["", "   ", "\t"], engine)

    assert engine.calls == []
    assert output == [cli.BANNER]


def test_empty_input_after_query_does_not_repeat_search():
    engine = FakeEngine({"typed": [result("Typed once.")]})

    output = run_cli(["typed", ""], engine)

    assert engine.calls == ["typed"]
    assert output == [
        cli.BANNER,
        "Here are 1 suggestions:",
        "1. Typed once. (example.txt:1, score=14)",
        "typed",
    ]


def test_prints_fewer_than_five_results_without_padding():
    engine = FakeEngine(
        {
            "short": [
                result("Alpha.", offset=1),
                result("Beta.", offset=2),
            ]
        }
    )

    output = run_cli(["short"], engine)

    assert engine.calls == ["short"]
    assert output == [
        cli.BANNER,
        "Here are 2 suggestions:",
        "1. Alpha. (example.txt:1, score=14)",
        "2. Beta. (example.txt:2, score=14)",
        "short",
    ]


def test_no_results_are_reported_without_crashing():
    engine = FakeEngine({"missing": []})

    output = run_cli(["missing"], engine)

    assert engine.calls == ["missing"]
    assert output == [
        cli.BANNER,
        cli.NO_MATCHES,
        "missing",
    ]


def test_result_formatting_matches_required_numbered_lines():
    engine = FakeEngine(
        {
            "this is": [
                result("Alpha: this is a demo.", "example.txt", 1, 14),
                result("Beta: this is a demo.", "example.txt", 2, 14),
            ]
        }
    )

    output = run_cli(["this is"], engine)

    assert output[1:4] == [
        "Here are 2 suggestions:",
        "1. Alpha: this is a demo. (example.txt:1, score=14)",
        "2. Beta: this is a demo. (example.txt:2, score=14)",
    ]


def test_main_loads_builds_creates_engine_and_runs_cli(monkeypatch):
    calls = []
    fake_corpus = object()
    fake_index = object()
    fake_engine = object()

    class FakeCorpusLoader:
        @classmethod
        def load(cls, root: Path):
            calls.append(("load", root))
            return fake_corpus

    class FakeIndexBuilder:
        @classmethod
        def build(cls, corpus):
            calls.append(("build", corpus))
            return fake_index

    class FakeAutoCompleteEngine:
        def __new__(cls, corpus, index):
            calls.append(("engine", corpus, index))
            return fake_engine

    def fake_run(engine):
        calls.append(("run", engine))

    monkeypatch.setattr(main_module, "Corpus", FakeCorpusLoader)
    monkeypatch.setattr(main_module, "InvertedIndex", FakeIndexBuilder)
    monkeypatch.setattr(main_module, "AutoCompleteEngine", FakeAutoCompleteEngine)
    monkeypatch.setattr(main_module, "run", fake_run)

    exit_code = main_module.main(["custom-corpus"])

    assert exit_code == 0
    assert calls == [
        ("load", Path("custom-corpus")),
        ("build", fake_corpus),
        ("engine", fake_corpus, fake_index),
        ("run", fake_engine),
    ]
