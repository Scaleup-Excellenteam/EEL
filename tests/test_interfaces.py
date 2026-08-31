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

    @pytest.mark.parametrize(
        "name", ["load", "__len__", "__getitem__", "normalized", "__iter__"]
    )
    def test_method_exists(self, name):
        assert callable(getattr(loader.Corpus, name))

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


# Still-stubbed entry points, grouped by owner. A stub that returns None instead
# of raising is how false green builds start, so each one is asserted to raise.
#
# WHEN YOU IMPLEMENT YOUR TRACK: delete your own key from this dict, nothing
# else. The keys are on separate lines precisely so that three developers can
# each remove theirs without ever touching the same line.
STILL_STUBBED: dict[str, list] = {
    # Elav (feature/scoring-core): implemented, entry removed.
    "qusai": [
        lambda: loader.Corpus.load("."),
        lambda: index.InvertedIndex.build(None),
    ],
    "monjed": [
        lambda: autocomplete.AutoCompleteEngine(None, None),
        lambda: cli.run(None),
        lambda: main.main([]),
    ],
}


class TestStubsFailLoudly:
    @pytest.mark.parametrize(
        "owner,call",
        [(owner, call) for owner, calls in STILL_STUBBED.items() for call in calls],
    )
    def test_raises_not_implemented(self, owner, call):
        with pytest.raises(NotImplementedError):
            call()


class TestImplementedTracks:
    """Smoke checks that an implemented track is actually wired up.

    Deliberately shallow — the real coverage lives in each track's own test
    files. This only catches "someone implemented it but broke the interface".
    """

    def test_normalizer_is_implemented(self):
        assert normalizer.normalize("To be, or NOT to be") == "to be or not to be"

    def test_scorer_is_implemented(self):
        assert scorer.score_exact(7) == 14
        first_tier = next(scorer.score_ladder("to be", "abcdefghijklmnopqrstuvwxyz "))
        assert first_tier == [scorer.Variant(text="to be", score=10)]
