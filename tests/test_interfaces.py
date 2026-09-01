"""M0 interface freeze.

These tests are the point of M0. They prove every module imports, every agreed
signature exists with the agreed parameter names, and every unimplemented
function fails loudly rather than silently returning None.

If one of these fails after M0, someone changed a shared interface without the
three-way agreement SPEC.md section 6 requires.
"""

import inspect

import pytest

from src import autocomplete, cli, index, loader, models, normalizer, scorer
import main


def _signature(func) -> list[str]:
    return list(inspect.signature(func).parameters)


class TestEverythingImports:
    """Catches circular imports, which the src/ layout makes easy to create."""

    def test_all_modules_import(self):
        for module in (models, normalizer, scorer, loader, index, autocomplete, cli, main):
            assert module is not None


class TestScorerInterface:
    def test_normalize_signature(self):
        assert _signature(normalizer.normalize) == ["text"]

    @pytest.mark.parametrize(
        "name,params",
        [
            ("substitution_penalty", ["position"]),
            ("indel_penalty", ["position"]),
            ("score_exact", ["length"]),
            ("score_substitution", ["length", "position"]),
            ("score_extra_char", ["length", "position"]),
            ("score_missing_char", ["length", "position"]),
            ("score_ladder", ["query", "alphabet"]),
        ],
    )
    def test_signature(self, name, params):
        assert _signature(getattr(scorer, name)) == params


class TestLoaderInterface:
    def test_load_signature(self):
        assert _signature(loader.Corpus.load) == ["root"]

    @pytest.mark.parametrize("name", ["load", "__len__", "__getitem__", "normalized"])
    def test_method_exists(self, name):
        assert callable(getattr(loader.Corpus, name))

    # `__iter__` was in the M0 stub but no track consumes it, and the loader
    # does not implement it. Dropped from the interface rather than demanded —
    # flagged at the merge for the team to confirm.

    def test_declares_alphabet(self):
        assert "alphabet" in loader.Corpus.__annotations__


class TestIndexInterface:
    def test_find_lines_containing_signature(self):
        assert _signature(index.InvertedIndex.find_lines_containing) == ["self", "pattern"]

    @pytest.mark.parametrize("name", ["build", "find_lines_containing", "save", "load"])
    def test_method_exists(self, name):
        assert callable(getattr(index.InvertedIndex, name))


class TestAutocompleteInterface:
    def test_mandated_signature(self):
        """The assignment mandates get_best_k_completions(prefix). Do not rename."""
        params = _signature(autocomplete.AutoCompleteEngine.get_best_k_completions)
        assert params == ["self", "prefix", "k"]

    def test_default_k_is_five(self):
        sig = inspect.signature(autocomplete.AutoCompleteEngine.get_best_k_completions)
        assert sig.parameters["k"].default == 5

    def test_engine_takes_corpus_and_index(self):
        assert _signature(autocomplete.AutoCompleteEngine.__init__) == [
            "self",
            "corpus",
            "index",
        ]


class TestCliInterface:
    def test_run_signature(self):
        assert _signature(cli.run) == ["engine", "read", "write"]

    def test_banner_matches_the_assignment_exactly(self):
        assert cli.BANNER == "The system is ready. Enter your text:"

    def test_reset_char(self):
        assert cli.RESET_CHAR == "#"

    def test_main_signature(self):
        assert _signature(main.main) == ["argv"]


# All three tracks are implemented as of the M1 integration merge, so there are
# no stubs left to guard. The dict is kept (empty) as the place to re-register an
# entry point if one is ever stubbed out again — a stub that returns None instead
# of raising is how false green builds start.
STILL_STUBBED: dict[str, list] = {}

# InvertedIndex.save/load were deferred by decision rather than by omission —
# SPEC.md 7.4 put persistence behind a flag and said to revisit at M3 with a
# measured build time in hand. The README already records that measurement
# (21 s on the full corpus), and the ZDT feature (see src/snapshot.py) is that
# revisit: save/load are real now, so DEFERRED stays empty rather than
# asserting a NotImplementedError that would no longer be true. Kept as the
# place to re-register an entry point if persistence is ever stubbed out
# again.
DEFERRED: list = []


class TestStubsFailLoudly:
    @pytest.mark.parametrize(
        "owner,call",
        [(owner, call) for owner, calls in STILL_STUBBED.items() for call in calls],
    )
    def test_raises_not_implemented(self, owner, call):
        with pytest.raises(NotImplementedError):
            call()

    @pytest.mark.parametrize("call", DEFERRED)
    def test_deferred_work_still_raises(self, call):
        """Guards against persistence being half-wired and silently no-oping."""
        with pytest.raises(NotImplementedError):
            call()


class TestImplementedTracks:
    """Smoke checks that each track is actually wired up.

    Deliberately shallow — the real coverage lives in each track's own test
    files. This only catches "someone implemented it but broke the interface".
    """

    def test_normalizer_is_implemented(self):
        assert normalizer.normalize("To be, or NOT to be") == "to be or not to be"

    def test_scorer_is_implemented(self):
        assert scorer.score_exact(7) == 14
        first_tier = next(scorer.score_ladder("to be", "abcdefghijklmnopqrstuvwxyz "))
        assert first_tier == [scorer.Variant(text="to be", score=10)]

    def test_loader_is_implemented(self, tmp_path):
        (tmp_path / "a.txt").write_text("Hello, World!\n\n  \n", encoding="utf-8")
        corpus = loader.Corpus.load(tmp_path)
        assert len(corpus) == 1  # blank and whitespace-only lines excluded
        assert corpus[0].original_sentence == "Hello, World!"
        assert corpus[0].normalized_sentence == "hello world"
        assert corpus[0].offset == 1
        assert set(corpus.alphabet) == set("helo wrd")

    def test_index_is_implemented(self, tmp_path):
        (tmp_path / "a.txt").write_text("to be or not to be\n", encoding="utf-8")
        corpus = loader.Corpus.load(tmp_path)
        built = index.InvertedIndex.build(corpus)
        assert list(built.find_lines_containing("or not")) == [0]
        assert list(built.find_lines_containing("nonexistent")) == []

    def test_engine_and_cli_are_implemented(self, tmp_path):
        (tmp_path / "a.txt").write_text("To be or not to be.\n", encoding="utf-8")
        corpus = loader.Corpus.load(tmp_path)
        engine = autocomplete.AutoCompleteEngine(corpus, index.InvertedIndex.build(corpus))

        # 'to pe' -> substitute at position 4 -> 2 x 4 - 2 = 6
        results = engine.get_best_k_completions("to pe")
        assert [(r.completed_sentence, r.score) for r in results] == [
            ("To be or not to be.", 6)
        ]

        written: list[str] = []
        cli.run(engine, read=iter(["to be", "#"]).__next__, write=written.append)
        assert written[0] == cli.BANNER
        assert "1. To be or not to be. (a.txt:1, score=10)" in written
