"""Additional tests for src/normalizer.py: non-ASCII input, which none of the
existing normalizer tests touch (they only ever feed it ASCII text)."""

from src.normalizer import normalize


def test_non_ascii_letters_are_stripped_like_punctuation():
    """Accented and other non-ASCII letters fall outside [a-z0-9 ] and are
    deleted the same way punctuation is — not transliterated, not kept."""
    assert normalize("café") == "caf"
    assert normalize("naïve") == "nave"
    assert normalize("ÀLPHA café") == "lpha caf"


def test_emoji_and_symbols_are_stripped_leaving_valid_words():
    assert normalize("emoji 🎉 here") == "emoji here"
    assert normalize("price: 5€ only") == "price 5 only"
