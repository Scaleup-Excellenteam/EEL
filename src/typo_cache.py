"""Cache of common typing mistakes, checked before the rest of a search.

Stores `typo -> (correct_word, frequency)`. This does not replace matching or
scoring. It only remembers misspellings already seen, so a later search can try
the known fix first among variants that already share the same score.
"""


class TypoCache:
    """Dictionary of typos to `(correct word, how often that typo appeared)`."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[str, int]] = {}

    def record(self, typo: str, correction: str) -> None:
        """Add a mistake, or increment its frequency if the typo is already known."""
        if not typo or not correction or typo == correction:
            return

        current = self._entries.get(typo)
        if current is None:
            self._entries[typo] = (correction, 1)
            return

        _stored_word, frequency = current
        self._entries[typo] = (correction, frequency + 1)

    def lookup(self, typo: str) -> tuple[str, int] | None:
        """Return `(correct_word, frequency)` for `typo`, or None if unknown."""
        return self._entries.get(typo)

    def record_match(self, query: str, corrected_query: str) -> None:
        """Record the word-level edits between a mistyped query and its correction."""
        for typo, correction in _edits(query, corrected_query):
            self.record(typo, correction)

    def preferred_texts(self, query: str) -> tuple[str, ...]:
        """Corrected query strings to try first among same-score variants."""
        preferred: list[str] = []
        seen: set[str] = set()

        def add(text: str) -> None:
            if text and text != query and text not in seen:
                seen.add(text)
                preferred.append(text)

        entry = self.lookup(query)
        if entry is not None:
            add(entry[0])

        tokens = query.split(" ")
        for index, token in enumerate(tokens):
            entry = self.lookup(token)
            if entry is None:
                continue
            replaced = list(tokens)
            replaced[index] = entry[0]
            add(" ".join(replaced))

        return tuple(preferred)

    def prioritize(self, query: str, variants: list) -> list:
        """Move known corrections to the front of a score group.

        Variants the search would not already have tried are ignored, so the
        cache never searches a string the original logic would not search.
        """
        preferred = set(self.preferred_texts(query))
        if not preferred:
            return variants
        return [variant for variant in variants if variant.text in preferred] + [
            variant for variant in variants if variant.text not in preferred
        ]


def _edits(mistyped: str, corrected: str) -> tuple[tuple[str, str], ...]:
    """The (typo, correction) pairs implied by one matched query variant.

    When the two strings have the same number of words, only the words that
    actually differ are stored — so `numpy arrray` vs `numpy array` records
    `arrray` → `array`, not the whole phrase. When word counts differ (a space
    was inserted or deleted), the full strings are stored instead.
    """
    if not mistyped or not corrected or mistyped == corrected:
        return ()

    mistyped_words = mistyped.split(" ")
    corrected_words = corrected.split(" ")
    if len(mistyped_words) == len(corrected_words):
        pairs = tuple(
            (typo, correction)
            for typo, correction in zip(mistyped_words, corrected_words)
            if typo != correction
        )
        if pairs:
            return pairs

    return ((mistyped, corrected),)
