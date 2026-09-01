"""Interactive loop. Owner: Monjed (feature/online-search).

M0 STUB — signatures frozen, implementation pending.

See specs/monjed-online-search.md section 4.
"""

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
    """Run the online loop until end of input.

    `read` and `write` are injected so the loop can be tested without a real
    terminal. Monjed may change this signature at the M0 review if he prefers a
    different testing seam — it is a proposal, not a decree.

    Required behaviour (assignment section "תוכנית שלמה"):

        state: current_text = ""

        print BANNER once
        loop:
            chunk = read()
            if chunk == RESET_CHAR:
                current_text = ""          # back to the initial state
                continue
            current_text += chunk          # ACCUMULATE, do not replace
            show the best 5 completions for current_text
            write(current_text)            # echo, so the user continues from
                                           # where they stopped

    The trailing echo is not decoration — it is the cursor position, and the
    assignment's sample output shows it explicitly.

    Output format, per the assignment's sample:

        The system is ready. Enter your text:
        this is
        Here are 5 suggestions:
        1. Alpha: this is a demo. (example.txt:1, score=14)
        ...
        this is

    Each suggestion line is `f"{rank}. {result}"`, where `result` is an
    `AutoCompleteData` rendered by its own `__str__`.

    Edge cases to handle:
      - empty input (bare Enter): do not crash, do not search
      - fewer than 5 matches: print what exists, do not pad
      - no matches at all: say so plainly, do NOT clear the accumulated text
      - `#` typed mid-word, and `#` typed when the query is already empty
      - whitespace-only input
    """
    raise NotImplementedError("Monjed — feature/online-search")
