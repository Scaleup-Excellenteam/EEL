"""Entry point. Owner: Monjed (feature/online-search).

M0 STUB — signature frozen, implementation pending.

This is what the grader runs. Keep it thin: wiring only, no logic. Anything
worth testing belongs in autocomplete.py or cli.py.

    python main.py [corpus_root]
"""

import sys
from pathlib import Path

# The assignment says the offline stage reads the text files "ממקום ידוע מראש" —
# from a location known in advance. This is that location; override via argv[1].
DEFAULT_CORPUS_ROOT = Path("Archive")


def main(argv: list[str] | None = None) -> int:
    """Run the offline stage, then hand control to the online loop.

        root = Path(argv[0]) if argv else DEFAULT_CORPUS_ROOT
        corpus = Corpus.load(root)          # offline
        index = InvertedIndex.build(corpus) # offline
        engine = AutoCompleteEngine(corpus, index)
        print(BANNER)                       # readiness banner
        run(engine)                         # online

    The banner prints only AFTER the build completes, which is why the build is
    user-visible and why its duration matters (SPEC.md 7.4).
    """
    raise NotImplementedError("Monjed — feature/online-search")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
