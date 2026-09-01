"""Tests for the ZDT offline->filesystem->online hand-off (src/snapshot.py)."""

from pathlib import Path

import pytest

from src import snapshot
from src.index import InvertedIndex

FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def test_current_version_dir_is_none_before_any_build(tmp_path: Path) -> None:
    assert snapshot.current_version_dir(tmp_path) is None


def test_load_current_is_none_before_any_build(tmp_path: Path) -> None:
    assert snapshot.load_current(tmp_path) is None


def test_build_snapshot_creates_a_versioned_directory_and_publishes_it(
    tmp_path: Path,
) -> None:
    snapshots_dir = tmp_path / "snapshots"

    version_dir = snapshot.build_snapshot(FIXTURE_ROOT, snapshots_dir)

    assert version_dir.is_dir()
    assert (version_dir / snapshot.SNAPSHOT_FILENAME).is_file()
    assert snapshot.current_version_dir(snapshots_dir) == version_dir


def test_load_current_returns_a_working_index_after_a_build(tmp_path: Path) -> None:
    snapshots_dir = tmp_path / "snapshots"
    snapshot.build_snapshot(FIXTURE_ROOT, snapshots_dir)

    index = snapshot.load_current(snapshots_dir)

    assert isinstance(index, InvertedIndex)
    assert list(index.find_lines_containing("this is a"))


def test_a_second_build_gets_its_own_directory_and_does_not_touch_the_first(
    tmp_path: Path,
) -> None:
    """Offline builds write to a fresh directory, never overwriting the
    currently-active snapshot in place — the whole point of the hand-off."""
    snapshots_dir = tmp_path / "snapshots"
    first_version_dir = snapshot.build_snapshot(FIXTURE_ROOT, snapshots_dir)
    first_snapshot_bytes = (first_version_dir / snapshot.SNAPSHOT_FILENAME).read_bytes()

    second_version_dir = snapshot.build_snapshot(FIXTURE_ROOT, snapshots_dir)

    assert second_version_dir != first_version_dir
    assert first_version_dir.is_dir()
    assert (
        first_version_dir / snapshot.SNAPSHOT_FILENAME
    ).read_bytes() == first_snapshot_bytes
    assert snapshot.current_version_dir(snapshots_dir) == second_version_dir


def test_publish_points_current_at_the_new_version_via_a_symlink(
    tmp_path: Path,
) -> None:
    """The pointer is a symlink swap so it can be repointed with one atomic
    rename, per ZDT's "atomic pointer" design."""
    snapshots_dir = tmp_path / "snapshots"
    version_dir = snapshot.build_snapshot(FIXTURE_ROOT, snapshots_dir)

    current_link = snapshots_dir / snapshot.CURRENT_LINK_NAME
    assert current_link.is_symlink()
    assert current_link.resolve() == version_dir.resolve()


def test_build_snapshot_does_not_publish_a_broken_snapshot(
    tmp_path: Path, monkeypatch
) -> None:
    """A build that fails validation must leave the previous `current` (or
    lack of one) untouched — an online reader must never be pointed at a
    snapshot that cannot actually be loaded."""
    snapshots_dir = tmp_path / "snapshots"

    def broken_load(path):
        raise ValueError("simulated corrupt snapshot")

    monkeypatch.setattr(snapshot.InvertedIndex, "load", staticmethod(broken_load))

    with pytest.raises(ValueError):
        snapshot.build_snapshot(FIXTURE_ROOT, snapshots_dir)

    assert snapshot.current_version_dir(snapshots_dir) is None


def test_new_version_ids_are_unique_and_sort_in_creation_order() -> None:
    first = snapshot._new_version_id()
    second = snapshot._new_version_id()

    assert first != second
    assert sorted([first, second]) == [first, second]
