"""ZDT: the offline->filesystem->online hand-off.

Owner: infrastructure (added for the ZDT initiative, on top of the
persistence extension point SPEC.md 7.4 always intended `InvertedIndex.save`/
`load` to be — see src/index.py).

Two processes never talk to each other directly. The offline stage
(`build_snapshot`, driven by `build_snapshot.py`) loads a corpus, builds an
index, and writes it into its own freshly named directory under
`snapshots_dir` — it never overwrites a directory another process might be
reading. Only once that write is verified to actually load back does it
publish it, by atomically repointing a `current` symlink at the new
directory. The online stage (`load_current`, and `LiveEngine` in
src/live_engine.py) only ever reads through that symlink, so it either sees
the previous snapshot in full or the new one in full — never a partial
write, and never a torn read.

That symlink is the entire hand-off. Nothing here talks to the online
process; nothing in the online process talks to the offline one. Adding a
new data source is: point `build_snapshot.py` at corpus data that includes
it (locally, or on a remote/shared mount if `snapshots_dir` lives on one) and
run it. The already-running service picks up the change the next time it
polls `current` — no restart, no coordination, no downtime window.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.index import InvertedIndex
from src.loader import Corpus

SNAPSHOT_FILENAME = "snapshot.index"
CURRENT_LINK_NAME = "current"


def build_snapshot(corpus_root: Path, snapshots_dir: Path) -> Path:
    """Offline stage: build a new snapshot from `corpus_root` and publish it.

    Writes to a new, uniquely named directory under `snapshots_dir` — the
    snapshot currently pointed to by `current`, if any, is never touched.
    The new snapshot is validated by loading it back before `current` is
    repointed at it, so a build that produced a broken file raises instead
    of ever becoming the one the online service reads.

    Returns the new version directory.
    """
    corpus = Corpus.load(corpus_root)
    index = InvertedIndex.build(corpus)

    snapshots_dir = Path(snapshots_dir)
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    version_dir = snapshots_dir / _new_version_id()
    version_dir.mkdir()
    index.save(version_dir / SNAPSHOT_FILENAME)

    # Validate before publishing: a build that wrote something InvertedIndex
    # itself cannot load back must never become `current`. Raises straight
    # through — the caller (build_snapshot.py) reports it and `current` is
    # left exactly as it was.
    InvertedIndex.load(version_dir / SNAPSHOT_FILENAME)

    _publish(snapshots_dir, version_dir)
    return version_dir


def current_version_dir(snapshots_dir: Path) -> Path | None:
    """Resolve the `current` pointer to a version directory, or None if no
    snapshot has ever been published under `snapshots_dir`."""
    link = Path(snapshots_dir) / CURRENT_LINK_NAME
    if not link.is_symlink():
        return None
    return link.resolve()


def load_current(snapshots_dir: Path) -> InvertedIndex | None:
    """Online stage: load whichever snapshot `current` names right now, or
    None if `snapshots_dir` has no published snapshot yet."""
    version_dir = current_version_dir(snapshots_dir)
    if version_dir is None:
        return None
    return InvertedIndex.load(version_dir / SNAPSHOT_FILENAME)


def _new_version_id() -> str:
    """A directory name that is unique per build and sorts in creation order.

    The timestamp alone would collide for two builds started in the same
    microsecond; the uuid suffix guarantees uniqueness regardless of clock
    resolution without affecting the sort order, since it only ever breaks a
    tie between two otherwise-identical timestamps.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def _publish(snapshots_dir: Path, version_dir: Path) -> None:
    """Atomically repoint `snapshots_dir/current` at `version_dir`.

    Builds a new symlink under a private temp name, then renames it over
    `current` with `os.replace` — one rename() syscall, so a reader resolving
    `current` at any instant sees either the old target or the new one,
    never a missing or half-written link.
    """
    link = snapshots_dir / CURRENT_LINK_NAME
    temp_link = snapshots_dir / f".{CURRENT_LINK_NAME}.{os.getpid()}.tmp"
    if temp_link.is_symlink() or temp_link.exists():
        temp_link.unlink()
    temp_link.symlink_to(version_dir.name)
    os.replace(temp_link, link)
