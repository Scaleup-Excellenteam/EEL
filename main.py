"""Entry point. Owner: Monjed (feature/online-search)."""

import sys
from pathlib import Path

from src.autocomplete import AutoCompleteEngine
from src.cli import run
from src.index import InvertedIndex
from src.loader import Corpus

# The assignment says the offline stage reads from a known location.
DEFAULT_CORPUS_ROOT = Path("Archive")


def main(argv: list[str] | None = None) -> int:
    """Run the offline stage, then hand control to the online loop."""
    args = [] if argv is None else argv
    root = Path(args[0]) if args else DEFAULT_CORPUS_ROOT

    corpus = Corpus.load(root)
    index = InvertedIndex.build(corpus)
    engine = AutoCompleteEngine(corpus, index)
    run(engine)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
