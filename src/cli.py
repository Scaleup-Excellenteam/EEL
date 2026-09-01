"""Interactive loop. Owner: Monjed (feature/online-search)."""

from collections.abc import Callable

from src.autocomplete import AutoCompleteEngine

BANNER = "The system is ready. Enter your text:"
SUGGESTIONS_HEADER = "Here are {n} suggestions:"
NO_MATCHES = "No suggestions found."
RESET_CHAR = "#"


def run(
    engine: AutoCompleteEngine,
    *,
    read: Callable[[], str] = input,
    write: Callable[[str], None] = print,
) -> None:
    """Run the online loop until end of input."""
    current_text = ""
    write(BANNER)

    while True:
        try:
            chunk = read()
        except (EOFError, StopIteration):
            return

        # A bare Enter typed nothing, so there is nothing new to search and the
        # previous results should not be reprinted.
        #
        # The guard tests `not chunk`, NOT `not chunk.strip()`. Those differ for
        # a whitespace-only chunk, and the difference was a bug: `.strip()`
        # discarded a typed space instead of appending it. Since the user's own
        # space is the only thing separating one chunk from the next, typing
        # "be", then " ", then "that" accumulated to "bethat" and scored 6 on a
        # spurious one-edit match, where "be that" scores 14. The space was not
        # merely unsearched — it was gone from `current_text` for the rest of the
        # sentence. A typed space is typed text.
        if not chunk:
            continue

        current_text = _apply_input(current_text, chunk)
        if not current_text.strip():
            continue

        suggestions = engine.get_best_k_completions(current_text)
        if suggestions:
            write(SUGGESTIONS_HEADER.format(n=len(suggestions)))
            for rank, suggestion in enumerate(suggestions, start=1):
                write(f"{rank}. {suggestion}")
        else:
            write(NO_MATCHES)

        write(current_text)


def _apply_input(current_text: str, chunk: str) -> str:
    """Apply one entered chunk, treating '#' as a sentence reset marker."""
    if RESET_CHAR not in chunk:
        return current_text + chunk

    return chunk.rsplit(RESET_CHAR, maxsplit=1)[1]
