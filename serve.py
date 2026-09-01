"""ZDT online stage entry point.

Serves the interactive CLI (src/cli.run) against whichever snapshot is
currently published under `snapshots_dir`, and keeps polling for a newer one
in the background -- see src/live_engine.py. A snapshot published later by
build_snapshot.py, from this machine or (if `snapshots_dir` is a shared
mount) a remote one, is picked up without restarting this process and
without interrupting a query already in flight.
"""

import sys
from pathlib import Path

from src.cli import run
from src.live_engine import LiveEngine

DEFAULT_SNAPSHOTS_DIR = Path("snapshots")


def main(argv: list[str] | None = None) -> int:
    """Serve from `argv[0]` (or DEFAULT_SNAPSHOTS_DIR) until end of input."""
    args = [] if argv is None else argv
    snapshots_dir = Path(args[0]) if args else DEFAULT_SNAPSHOTS_DIR

    live_engine = LiveEngine(snapshots_dir)
    if live_engine.engine is None:
        print(
            f"No snapshot published under {snapshots_dir} yet. "
            "Run `python build_snapshot.py` first.",
            file=sys.stderr,
        )
        return 1

    try:
        run(live_engine)
    finally:
        live_engine.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
