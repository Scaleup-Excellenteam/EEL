"""Acceptance tests: one assertion per requirement stated in the assignment.

Every other test file checks a module. This one checks the ASSIGNMENT — it walks
the requirements in order and demonstrates each against the assembled system, so
that conformance is a thing we run rather than a thing we believe.

If a requirement here fails, the submission is wrong regardless of how many unit
tests pass. Read it alongside the assignment, not alongside the code.
"""

import dataclasses
import inspect
import subprocess
import sys
from pathlib import Path

import pytest

import main as main_module
from src import cli
from src.autocomplete import AutoCompleteEngine
from src.index import InvertedIndex
from src.loader import Corpus
from src.models import AutoCompleteData
from src.normalizer import normalize
from src.scorer import (
    INDEL_PENALTIES,
    SUBSTITUTION_PENALTIES,
    score_exact,
    score_extra_char,
    score_missing_char,
    score_substitution,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# The assignment's own sample corpus, plus a nested tree and the Shakespeare
# sentence its worked examples are based on.
EXAMPLE_LINES = [f"{name}: this is a demo." for name in ("Alpha", "Beta", "Delta", "Gamma", "Omega")]
SHAKESPEARE = "To be or not to be, that is the question."


@pytest.fixture(scope="module")
def corpus_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("corpus")
    (root / "a" / "b").mkdir(parents=True)
    (root / "example.txt").write_text("\n".join(EXAMPLE_LINES) + "\n", encoding="utf-8")
    # blank and whitespace-only lines must be excluded
    (root / "a" / "mid.txt").write_text(f"{SHAKESPEARE}\n\n   \n", encoding="utf-8")
    (root / "a" / "b" / "deep.txt").write_text(
        "Nested   deeply,    with  MANY spaces!\n", encoding="utf-8"
    )
    return root


@pytest.fixture(scope="module")
def engine(corpus_root):
    corpus = Corpus.load(corpus_root)
    return AutoCompleteEngine(corpus, InvertedIndex.build(corpus))


@pytest.fixture(scope="module")
def corpus(corpus_root):
    return Corpus.load(corpus_root)


def _session(engine, chunks):
    """Drive the CLI with a scripted sequence of typed chunks."""
    written: list[str] = []
    chunk_iter = iter(chunks)
    cli.run(engine, read=lambda: next(chunk_iter), write=written.append)
    return written


class TestOfflineStage:
    """"שלב ראשון (offline) ... קוראת את קבצי הטקסט (ממקום ידוע מראש)" """

    def test_reads_txt_files_recursively_at_every_depth(self, corpus):
        sources = {corpus[i].source_text for i in range(len(corpus))}
        assert sources == {"example.txt", "a/mid.txt", "a/b/deep.txt"}

    def test_a_sentence_is_one_full_line(self, corpus):
        assert corpus[0].original_sentence == EXAMPLE_LINES[0]

    def test_blank_and_whitespace_only_lines_are_excluded(self, corpus):
        assert len(corpus) == len(EXAMPLE_LINES) + 2

    def test_alphabet_is_derived_from_the_corpus(self, corpus):
        assert corpus.alphabet and set(corpus.alphabet) <= set("abcdefghijklmnopqrstuvwxyz0123456789 ")


class TestMandatedApi:
    """The signature and dataclass the assignment dictates verbatim."""

    def test_get_best_k_completions_signature(self):
        params = list(inspect.signature(AutoCompleteEngine.get_best_k_completions).parameters)
        assert params[:2] == ["self", "prefix"]

    def test_autocompletedata_has_exactly_the_four_mandated_fields(self):
        assert [f.name for f in dataclasses.fields(AutoCompleteData)] == [
            "completed_sentence",
            "source_text",
            "offset",
            "score",
        ]


class TestNormalizationRules:
    """"אין צורך שהמשתמש ידייק ... אותיות גדולות\\קטנות או סימני פיסוק ...
    בנוסף אין הגבלה על מספר הרווחים בין המילים" """

    def test_case_insensitive(self):
        assert normalize("To BE") == normalize("to be")

    def test_punctuation_ignored_and_deleted_not_spaced(self):
        assert normalize("be, that") == "be that"
        assert len(normalize("be, that")) == 7  # 14 = 2 x 7

    def test_any_number_of_spaces_is_equivalent(self):
        forms = ["be that", "be, that", "be              that"]
        assert len({normalize(form) for form in forms}) == 1

    def test_digits_are_preserved(self):
        assert normalize("2o be") == "2o be"


class TestScoringAgainstEveryWorkedExample:
    """All twelve: seven in the English appendix, five in the Hebrew body."""

    def test_penalty_tables_match_the_assignment(self):
        assert SUBSTITUTION_PENALTIES == (5, 4, 3, 2, 1)
        assert INDEL_PENALTIES == (10, 8, 6, 4, 2)

    @pytest.mark.parametrize("query,expected", [("To be", 10), ("or Not", 12), ("be, that", 14)])
    def test_english_exact(self, query, expected):
        assert score_exact(len(normalize(query))) == expected

    @pytest.mark.parametrize("query,position,expected", [("2o be", 1, 3), ("to pe", 4, 6)])
    def test_english_substitution(self, query, position, expected):
        assert score_substitution(len(normalize(query)), position) == expected

    def test_english_extra_character(self):
        assert score_extra_char(len(normalize("or knot")), 4) == 8

    def test_english_missing_character(self):
        assert score_missing_char(len(normalize("or nt")), 5) == 8

    def test_hebrew_exact(self):
        assert score_exact(11) == 22

    @pytest.mark.parametrize("position,expected", [(11, 19), (4, 18)])
    def test_hebrew_substitution(self, position, expected):
        assert score_substitution(11, position) == expected

    def test_hebrew_extra_character(self):
        assert score_extra_char(12, 4) == 18

    def test_hebrew_missing_character(self):
        assert score_missing_char(10, 3) == 14


class TestMatchingRules:
    """"תת-מחרוזת של הפסוק (זה כולל התחלה, אמצע או סוף)" and one edit maximum."""

    def test_matches_a_substring_anywhere_not_only_a_prefix(self, engine):
        assert engine.get_best_k_completions("that is the")

    def test_one_substitution_matches(self, engine):
        assert engine.get_best_k_completions("to pe")[0].score == 6

    def test_one_extra_character_matches(self, engine):
        assert engine.get_best_k_completions("or knot")[0].score == 8

    def test_one_missing_character_matches(self, engine):
        assert engine.get_best_k_completions("or nt")[0].score == 8

    def test_two_edits_is_not_a_match(self, engine):
        """The appendix marks 'not be' N/A against this sentence."""
        assert engine.get_best_k_completions("not be") == []


@pytest.fixture(scope="module")
def results(engine):
    """The assignment's own sample query against its own sample corpus."""
    return engine.get_best_k_completions("this is")


class TestOutputRequirements:
    """"הפלט ... שורה מתוך קבצי המקור בצורתו המקורית ... ויכלול את הנתיב של הקובץ" """

    def test_returns_five_results(self, results):
        assert len(results) == 5

    def test_equal_scores_sort_alphabetically(self, results):
        assert {r.score for r in results} == {14}
        assert [r.completed_sentence.split(":")[0] for r in results] == [
            "Alpha", "Beta", "Delta", "Gamma", "Omega",
        ]

    def test_shows_the_original_line_including_punctuation(self, results):
        assert results[0].completed_sentence == "Alpha: this is a demo."

    def test_includes_the_file_path(self, results):
        assert results[0].source_text == "example.txt"

    def test_offset_is_the_one_based_line_number(self, results):
        assert [r.offset for r in results] == [1, 2, 3, 4, 5]

    def test_display_form_matches_the_assignment_sample_line(self, results):
        assert str(results[0]) == "Alpha: this is a demo. (example.txt:1, score=14)"

    def test_a_sloppily_typed_query_still_finds_its_line(self, engine):
        """Normalization must make spacing and punctuation irrelevant end to end."""
        found = engine.get_best_k_completions("Nested deeply with many spaces")
        assert len(found) == 1
        assert found[0].score == 60  # 30 normalized characters


class TestCliBehaviour:
    """"ברגע שהמשתמש מקליד תווים ולוחץ על Enter ... לאחר הצגת ההשלמות, המערכת
    מאפשרת למשתמש להמשיך להקליד מהמקום שבו הוא עצר ... אם המשתמש מקליד '#'" """

    def test_banner_is_printed_once_and_first(self, engine):
        written = _session(engine, ["this is"])
        assert written[0] == "The system is ready. Enter your text:"
        assert written.count("The system is ready. Enter your text:") == 1

    def test_suggestions_are_numbered_one_to_five(self, engine):
        written = _session(engine, ["this is"])
        assert written[2].startswith("1. ")
        assert written[6].startswith("5. ")

    def test_accumulated_text_is_echoed_after_the_results(self, engine):
        assert _session(engine, ["this is"])[-1] == "this is"

    def test_typed_text_accumulates_across_enter_presses(self, engine):
        assert _session(engine, ["this is", " a demo"])[-1] == "this is a demo"

    def test_a_typed_space_is_accumulated_not_discarded(self, engine):
        """Regression: the blank guard used to run before accumulation, so a
        typed space vanished and 'be' + ' ' + 'that' became 'bethat'."""
        assert _session(engine, ["be", " ", "that"])[-1] == "be that"

    def test_hash_returns_to_the_initial_state(self, engine):
        written = _session(engine, ["this is", " a demo", "#", "or Not"])
        assert written[-1] == "or Not"

    def test_no_matches_is_stated_plainly(self, engine):
        assert cli.NO_MATCHES in _session(engine, ["zzzqqqnothing"])

    def test_fewer_than_five_matches_are_not_padded(self, engine):
        written = _session(engine, ["that is the"])
        numbered = [line for line in written if line[:2] in {"1.", "2.", "3.", "4.", "5."}]
        assert 0 < len(numbered) < 5


class TestEntryPoint:
    """"עליכם לספק תוכנית אשר רצה בשני שלבים" — one program, both stages."""

    def test_main_runs_both_stages_end_to_end(self, corpus_root):
        result = subprocess.run(
            [sys.executable, "main.py", str(corpus_root)],
            input="this is\n",
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env={"PYTHONPATH": "."},
        )
        assert "The system is ready. Enter your text:" in result.stdout
        assert "1. Alpha: this is a demo. (example.txt:1, score=14)" in result.stdout

    def test_main_accepts_a_corpus_root_argument(self):
        assert list(inspect.signature(main_module.main).parameters) == ["argv"]
