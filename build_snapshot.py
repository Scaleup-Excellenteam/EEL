"""ZDT offline stage entry point.

Run this any time new or updated corpus data is ready to go live -- adding a
data source is exactly this: point it at corpus data that includes the new
files (locally, or on a remote/shared mount if `snapshots_dir` lives on one)
and run it. It builds a new snapshot into its own directory and publishes it
by atomically repointing `snapshots_dir/current`. A `serve.py` process
already running against `snapshots_dir` picks up the change on its own --
this script never talks to it directly. See src/snapshot.py.
"""

import sys
from pathlib import Path

from src.snapshot import build_snapshot

DEFAULT_CORPUS_ROOT = Path("Archive")
DEFAULT_SNAPSHOTS_DIR = Path("snapshots")


def main(argv: list[str] | None = None) -> int:
    """Build a snapshot from `argv[0]` (or DEFAULT_CORPUS_ROOT) and publish
    it under `argv[1]` (or DEFAULT_SNAPSHOTS_DIR)."""
    args = [] if argv is None else argv
    corpus_root = Path(args[0]) if len(args) > 0 else DEFAULT_CORPUS_ROOT
    snapshots_dir = Path(args[1]) if len(args) > 1 else DEFAULT_SNAPSHOTS_DIR

    version_dir = build_snapshot(corpus_root, snapshots_dir)
    print(f"Published snapshot '{version_dir.name}' as current in {snapshots_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
