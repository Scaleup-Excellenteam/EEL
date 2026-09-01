"""Additional tests for the private variant-building helpers in src/scorer.py.

`_variants_for` is only ever exercised indirectly through `score_ladder` in
the existing suite. These two tests pin down it directly: the append-after-
the-end edge for a missing character (the off-by-one trap the module's own
docstring warns about for `score_missing_char`), and the guarantee that a
substitution never regenerates the character it's replacing.
"""

from src.scorer import _variants_for


def test_variants_for_missing_can_append_after_the_last_character():
    """position = len(query) + 1 inserts past the last character, not before it."""
    variants = list(_variants_for("cat", "dxz", "missing", 4))

    assert variants == ["catd", "catx", "catz"]


def test_variants_for_substitution_never_reintroduces_the_original_character():
    variants = list(_variants_for("cat", "abc", "substitution", 1))

    assert variants == ["aat", "bat"]
    assert "cat" not in variants
