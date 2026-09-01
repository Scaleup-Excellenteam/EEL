"""Additional tests for src/loader.py: empty-corpus edges and the raw
constructor, none of which the existing loader tests exercise (they all go
through a fixture directory that has matching .txt files)."""

from pathlib import Path

from src.loader import Corpus


def test_load_with_no_txt_files_returns_empty_corpus(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_text("hello world", encoding="utf-8")
    (tmp_path / "data.csv").write_text("a,b,c\n", encoding="utf-8")

    corpus = Corpus.load(tmp_path)

    assert len(corpus) == 0
    assert corpus.alphabet == ""


def test_load_on_completely_empty_directory_returns_empty_corpus(tmp_path: Path) -> None:
    corpus = Corpus.load(tmp_path)

    assert len(corpus) == 0
    assert corpus.alphabet == ""


def test_corpus_constructed_directly_serves_getitem_and_normalized() -> None:
    """Bypasses Corpus.load entirely, exercising __init__/__len__/__getitem__/
    normalized() against data supplied by hand rather than by the loader."""
    corpus = Corpus(
        originals=("Hi there.", "Bye now."),
        normalized_sentences=("hi there", "bye now"),
        sources=("greetings.txt", "greetings.txt"),
        offsets=(1, 2),
        alphabet="abehinortwy ",
    )

    assert len(corpus) == 2
    assert corpus.alphabet == "abehinortwy "
    first = corpus[0]
    assert first.original_sentence == "Hi there."
    assert first.normalized_sentence == "hi there"
    assert first.source_text == "greetings.txt"
    assert first.offset == 1
    assert corpus.normalized(1) == "bye now"
