"""Tests for the Streamlit entry point in app.py.

app.py had no test coverage at all before this file. `main()` is driven
through Streamlit's own `AppTest` harness (streamlit.testing.v1), which runs
the script and exposes its rendered elements without a browser. `load_engine`
is exercised directly, since it is a plain function underneath the
`@st.cache_resource` decorator.
"""

from pathlib import Path

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

import app as app_module  # noqa: E402

APP_PATH = str(Path(app_module.__file__).resolve())


def _write_archive(root: Path, lines: dict[str, str]) -> Path:
    archive = root / "Archive"
    archive.mkdir()
    for filename, content in lines.items():
        (archive / filename).write_text(content, encoding="utf-8")
    return archive


def test_missing_archive_folder_shows_error_and_no_crash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    at = AppTest.from_file(APP_PATH)
    at.run()

    assert not at.exception
    assert len(at.error) == 1
    assert "Archive folder not found" in at.error[0].value


def test_title_and_instructions_render_before_any_search(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_archive(tmp_path, {"a.txt": "Hello there.\n"})

    at = AppTest.from_file(APP_PATH)
    at.run()

    assert not at.exception
    assert [t.value for t in at.title] == ["EEL Autocomplete"]
    assert at.error == []
    assert at.subheader == []


def test_clicking_search_with_empty_query_shows_prompt_to_enter_text(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_archive(tmp_path, {"a.txt": "Hello there.\n"})

    at = AppTest.from_file(APP_PATH)
    at.run()
    at.button[0].click().run()

    assert not at.exception
    assert [i.value for i in at.info] == ["Enter some text before searching."]


def test_clicking_search_with_whitespace_only_query_shows_prompt_to_enter_text(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    _write_archive(tmp_path, {"a.txt": "Hello there.\n"})

    at = AppTest.from_file(APP_PATH)
    at.run()
    at.text_input[0].set_value("   ").run()
    at.button[0].click().run()

    assert not at.exception
    assert [i.value for i in at.info] == ["Enter some text before searching."]


def test_typing_without_clicking_search_does_not_run_a_search(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_archive(tmp_path, {"a.txt": "Alpha: this is a demo.\n"})

    at = AppTest.from_file(APP_PATH)
    at.run()
    at.text_input[0].set_value("this is").run()

    assert not at.exception
    assert at.subheader == []
    assert at.info == []


def test_successful_search_shows_ranked_results_with_metadata(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_archive(
        tmp_path,
        {"a.txt": "Alpha: this is a demo.\nBeta: this is a demo.\n"},
    )

    at = AppTest.from_file(APP_PATH)
    at.run()
    at.text_input[0].set_value("this is").run()
    at.button[0].click().run()

    assert not at.exception
    assert [s.value for s in at.subheader] == ["Top 2 results"]
    assert [t.value for t in at.text] == [
        "Alpha: this is a demo.",
        "Beta: this is a demo.",
    ]
    captions = [c.value for c in at.caption]
    assert captions[0] == "Source file: a.txt | Offset / line number: 1 | Score: 14"
    assert captions[1] == "Source file: a.txt | Offset / line number: 2 | Score: 14"


def test_search_with_no_matches_shows_no_results_message(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_archive(tmp_path, {"a.txt": "Alpha: this is a demo.\n"})

    at = AppTest.from_file(APP_PATH)
    at.run()
    at.text_input[0].set_value("zzzqqqnothing").run()
    at.button[0].click().run()

    assert not at.exception
    assert [i.value for i in at.info] == ["No results found."]
    assert at.subheader == []


def test_load_engine_builds_corpus_and_index_and_wires_engine(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("Alpha: this is a demo.\n", encoding="utf-8")

    app_module.load_engine.clear()
    engine = app_module.load_engine(str(tmp_path))

    assert isinstance(engine, app_module.AutoCompleteEngine)
    assert len(engine.corpus) == 1
    assert list(engine.index.find_lines_containing("this is")) == [0]
    app_module.load_engine.clear()
