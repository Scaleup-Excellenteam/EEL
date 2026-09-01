from dataclasses import dataclass
import importlib
from pathlib import Path
import re
import sys
from types import ModuleType


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

from src import loader as loader_module  # noqa: E402
from src.loader import Corpus  # noqa: E402
from src.normalizer import normalize  # noqa: E402


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def test_loads_fixture_recursively_and_preserves_line_metadata() -> None:
    corpus = Corpus.load(FIXTURE_ROOT)

    assert len(corpus) == 14
    records = [corpus[line_id] for line_id in range(len(corpus))]
    assert "ignored.md" not in {record.source_text for record in records}
    assert {record.source_text for record in records} == {
        "example.txt",
        "root.txt",
        "nested/middle.txt",
        "nested/deep/leaf.txt",
    }

    mixed = next(
        record for record in records if record.original_sentence == "Mixed CASE stays Displayed."
    )
    assert mixed.source_text == "root.txt"
    assert mixed.offset == 4
    assert mixed.normalized_sentence == normalize(mixed.original_sentence)
    assert all(record.original_sentence not in {"", "!!!"} for record in records)


def test_line_ids_follow_shared_normalized_sentence_ordering_contract() -> None:
    """The contract is keyed on normalized_sentence, NOT the raw original line.

    This test previously asserted `original_sentence.casefold()` and passed only
    because this fixture happens to order the same way under both keys. On the
    real corpus they differ sharply: 40% of lines are indented, and sorting on
    the raw line let leading whitespace outrank every letter, which silently
    dropped alphabetically earlier equal-scoring matches out of the top 5.
    """
    corpus = Corpus.load(FIXTURE_ROOT)
    records = [corpus[line_id] for line_id in range(len(corpus))]
    actual_keys = [
        (record.normalized_sentence, record.source_text, record.offset)
        for record in records
    ]

    assert actual_keys == sorted(actual_keys)
    assert records[0].original_sentence == "Alpha: this is a demo."
    example_records = [
        record for record in records if record.source_text == "example.txt"
    ]
    assert [
        (record.original_sentence, record.source_text, record.offset)
        for record in example_records
    ] == [
        ("Alpha: this is a demo.", "example.txt", 1),
        ("Beta: this is a demo.", "example.txt", 2),
        ("Delta: this is a demo.", "example.txt", 3),
        ("Gamma: this is a demo.", "example.txt", 4),
        ("Omega: this is a demo.", "example.txt", 5),
    ]


def test_indentation_does_not_decide_line_id_order(tmp_path) -> None:
    """Regression guard for the tie-break bug, on data that distinguishes the keys.

    Under the old `original_sentence.casefold()` key this would order
    Zeta, Yak, Beta, Alpha — indentation and '>' first, letters last.
    """
    (tmp_path / "doc.txt").write_text(
        "Alpha calls the parser.\n"
        "    Zeta calls the parser.\n"
        "\tYak calls the parser.\n"
        ">>> Beta calls the parser.\n",
        encoding="utf-8",
    )
    corpus = Corpus.load(tmp_path)
    leading_words = [
        corpus[line_id].normalized_sentence.split()[0]
        for line_id in range(len(corpus))
    ]

    assert leading_words == ["alpha", "beta", "yak", "zeta"]


def test_ordering_details_on_the_fixture_corpus() -> None:
    corpus = Corpus.load(FIXTURE_ROOT)
    records = [corpus[line_id] for line_id in range(len(corpus))]

    line_ids = {
        record.original_sentence: line_id
        for line_id, record in enumerate(records)
    }
    zebra = records[line_ids["Zebra arrives last."]]
    mixed = records[line_ids["Mixed CASE stays Displayed."]]
    assert zebra.offset == 1
    assert mixed.offset == 4
    assert line_ids["Zebra arrives last."] > line_ids["Mixed CASE stays Displayed."]

    duplicate_records = [
        record
        for record in records
        if record.original_sentence == "Shared sentence across files."
    ]
    assert [(record.source_text, record.offset) for record in duplicate_records] == [
        ("nested/deep/leaf.txt", 1),
        ("root.txt", 5),
    ]


def test_alphabet_and_normalized_accessor_are_derived_from_retained_text() -> None:
    corpus = Corpus.load(FIXTURE_ROOT)
    expected_alphabet = "".join(
        sorted(
            {
                character
                for line_id in range(len(corpus))
                for character in corpus.normalized(line_id)
            }
        )
    )

    assert corpus.alphabet == expected_alphabet
    assert "1" in corpus.alphabet
    assert " " in corpus.alphabet
    assert "!" not in corpus.alphabet
    for line_id in range(len(corpus)):
        assert corpus.normalized(line_id) == corpus[line_id].normalized_sentence


def test_calls_normalize_and_removes_only_line_terminators(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[str] = []

    def fake_normalize(text: str) -> str:
        calls.append(text)
        return "" if text in {"", "!!!"} else text.casefold()

    monkeypatch.setattr(loader_module, "normalize", fake_normalize)
    (tmp_path / "input.txt").write_bytes(
        b"  Keep surrounding spaces  \r\n!!!\nNo final newline"
    )
    (tmp_path / "ignored.csv").write_text("not loaded", encoding="utf-8")

    corpus = Corpus.load(tmp_path)

    assert calls == ["  Keep surrounding spaces  ", "!!!", "No final newline"]
    assert {corpus[index].original_sentence for index in range(len(corpus))} == {
        "  Keep surrounding spaces  ",
        "No final newline",
    }


def test_invalid_utf8_is_replaced_before_normalization(
    tmp_path: Path, monkeypatch
) -> None:
    decoded_lines: list[str] = []

    def recording_normalize(text: str) -> str:
        decoded_lines.append(text)
        return text.casefold()

    monkeypatch.setattr(loader_module, "normalize", recording_normalize)
    (tmp_path / "invalid.txt").write_bytes(b"valid first line\ninvalid: \xff byte\n")

    corpus = Corpus.load(tmp_path)
    replacement_text = "invalid: \ufffd byte"
    replacement_record = next(
        corpus[line_id]
        for line_id in range(len(corpus))
        if "\ufffd" in corpus[line_id].original_sentence
    )

    assert decoded_lines == ["valid first line", replacement_text]
    assert replacement_record.original_sentence == replacement_text
    assert replacement_record.normalized_sentence == replacement_text
    assert replacement_record.source_text == "invalid.txt"
    assert replacement_record.offset == 2
