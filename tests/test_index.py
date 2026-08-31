from dataclasses import dataclass
import importlib
from pathlib import Path
import re
import sys
from types import GeneratorType, ModuleType

import pytest


def _install_m0_stubs() -> None:
    try:
        importlib.import_module("src.models")
    except ModuleNotFoundError as error:
        if error.name != "src.models":
            raise
        models = ModuleType("src.models")

        @dataclass(frozen=True)
        class SentenceData:
            original_sentence: str
            normalized_sentence: str
            source_text: str
            offset: int

        models.SentenceData = SentenceData
        sys.modules["src.models"] = models

    try:
        importlib.import_module("src.normalizer")
    except ModuleNotFoundError as error:
        if error.name != "src.normalizer":
            raise
        normalizer = ModuleType("src.normalizer")

        def normalize(text: str) -> str:
            cleaned = re.sub(r"[^a-z0-9\s]", "", text.lower())
            return " ".join(cleaned.split())

        normalizer.normalize = normalize
        sys.modules["src.normalizer"] = normalizer


_install_m0_stubs()

from src.index import InvertedIndex, _strictly_interior_tokens  # noqa: E402
from src.loader import Corpus  # noqa: E402


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


@pytest.fixture
def corpus() -> Corpus:
    return Corpus.load(FIXTURE_ROOT)


def _brute_force(corpus: Corpus, pattern: str) -> list[int]:
    return [
        line_id
        for line_id in range(len(corpus))
        if pattern in corpus.normalized(line_id)
    ]


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        ("or no", ()),
        ("or not the", ("not",)),
        (" hello ", ("hello",)),
        ("one two three", ("two",)),
        (" one two ", ("one", "two")),
        ("single", ()),
    ],
)
def test_strictly_interior_token_detection(
    pattern: str, expected: tuple[str, ...]
) -> None:
    assert _strictly_interior_tokens(pattern) == expected


@pytest.mark.parametrize(
    "pattern",
    [
        "numbers",
        "bers 123 sur",
        "this is a",
        "alpha this is a demo",
        "or no",
        " this is",
        "is a ",
        "shared sentence across files",
        "not present anywhere",
        "deeply nested text",
        "this is a demo",
        "a",
        "punctuationheavy commas dots and symbols",
        "mixed case",
        "case stays",
    ],
)
def test_matches_brute_force_truth_in_ascending_order(
    corpus: Corpus, pattern: str
) -> None:
    index = InvertedIndex.build(corpus)
    expected = _brute_force(corpus, pattern)

    actual = list(index.find_lines_containing(pattern))

    assert actual == expected
    assert actual == sorted(actual)


def test_pattern_is_already_normalized(corpus: Corpus) -> None:
    index = InvertedIndex.build(corpus)

    assert list(index.find_lines_containing("mixed case"))
    assert list(index.find_lines_containing("Mixed CASE")) == []


def test_identical_lines_in_different_files_keep_distinct_ids(corpus: Corpus) -> None:
    index = InvertedIndex.build(corpus)

    matches = list(index.find_lines_containing("shared sentence across files"))

    assert len(matches) == 2
    assert matches[0] != matches[1]
    assert {corpus[line_id].source_text for line_id in matches} == {
        "nested/deep/leaf.txt",
        "root.txt",
    }


def test_indexed_lookup_uses_rarest_interior_word() -> None:
    class TrackingCorpus:
        def __init__(self) -> None:
            self.visited: list[int] = []
            self.sentences = (
                "start common rare end",
                "start common other end",
                "start common last end",
            )

        def __len__(self) -> int:
            return len(self.sentences)

        def normalized(self, line_id: int) -> str:
            self.visited.append(line_id)
            return self.sentences[line_id]

    corpus = TrackingCorpus()
    index = InvertedIndex.build(corpus)  # type: ignore[arg-type]
    corpus.visited.clear()

    assert list(index.find_lines_containing("start common rare end")) == [0]
    assert corpus.visited == [0]


def test_missing_interior_word_returns_without_candidate_access() -> None:
    class TrackingCorpus:
        def __init__(self) -> None:
            self.visited: list[int] = []

        def __len__(self) -> int:
            return 2

        def normalized(self, line_id: int) -> str:
            self.visited.append(line_id)
            return ("start known end", "another known line")[line_id]

    corpus = TrackingCorpus()
    index = InvertedIndex.build(corpus)  # type: ignore[arg-type]
    corpus.visited.clear()

    assert list(index.find_lines_containing("start absent end")) == []
    assert corpus.visited == []


def test_indexed_lookup_is_lazy() -> None:
    class TrackingCorpus:
        def __init__(self) -> None:
            self.visited: list[int] = []
            self.sentences = (
                "start anchor target end",
                "start anchor target end again",
                "start anchor target end last",
            )

        def __len__(self) -> int:
            return len(self.sentences)

        def normalized(self, line_id: int) -> str:
            self.visited.append(line_id)
            return self.sentences[line_id]

    corpus = TrackingCorpus()
    index = InvertedIndex.build(corpus)  # type: ignore[arg-type]
    corpus.visited.clear()
    matches = index.find_lines_containing("start anchor target")

    assert isinstance(matches, GeneratorType)
    assert corpus.visited == []
    assert next(matches) == 0
    assert corpus.visited == [0]
    matches.close()


def test_no_interior_token_fallback_is_lazy() -> None:
    class TrackingCorpus:
        def __init__(self) -> None:
            self.visited: list[int] = []

        def __len__(self) -> int:
            return 3

        def normalized(self, line_id: int) -> str:
            self.visited.append(line_id)
            return ("match", "later match", "last")[line_id]

    corpus = TrackingCorpus()
    index = InvertedIndex.build(corpus)  # type: ignore[arg-type]
    corpus.visited.clear()
    matches = index.find_lines_containing("match")

    assert next(matches) == 0
    assert corpus.visited == [0]
    matches.close()


def test_repeated_word_adds_line_id_to_posting_only_once() -> None:
    class RepeatedWordCorpus:
        def __len__(self) -> int:
            return 1

        def normalized(self, line_id: int) -> str:
            return "start repeat repeat repeat end"

    index = InvertedIndex.build(RepeatedWordCorpus())  # type: ignore[arg-type]

    assert list(index.find_lines_containing("start repeat end")) == []
    assert list(index.find_lines_containing(" repeat ")) == [0]


def test_persistence_is_deferred_to_m3(corpus: Corpus, tmp_path: Path) -> None:
    index = InvertedIndex.build(corpus)

    with pytest.raises(NotImplementedError):
        index.save(tmp_path / "index.bin")
    with pytest.raises(NotImplementedError):
        InvertedIndex.load(tmp_path / "index.bin")
