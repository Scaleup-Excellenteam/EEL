"""Tests for LiveEngine, the online half of the ZDT hand-off (src/live_engine.py).

LiveEngine duck-types `AutoCompleteEngine.get_best_k_completions`, so it drops
straight into the existing `src/cli.run` loop unmodified — see src/serve.py.
"""

import time
from pathlib import Path

from src import snapshot
from src.live_engine import LiveEngine

FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def _make_second_corpus(tmp_path: Path) -> Path:
    """A corpus root distinguishable from the fixtures by a unique sentence."""
    root = tmp_path / "second-corpus"
    root.mkdir()
    (root / "extra.txt").write_text("A brand new data source arrived.\n", encoding="utf-8")
    return root


def test_engine_is_none_when_no_snapshot_exists_yet(tmp_path: Path) -> None:
    live = LiveEngine(tmp_path / "snapshots", autostart=False)

    assert live.engine is None


def test_loads_whatever_snapshot_is_current_on_construction(tmp_path: Path) -> None:
    snapshots_dir = tmp_path / "snapshots"
    snapshot.build_snapshot(FIXTURE_ROOT, snapshots_dir)

    live = LiveEngine(snapshots_dir, autostart=False)

    assert live.engine is not None
    assert live.get_best_k_completions("this is a")


def test_refresh_returns_false_when_the_pointer_has_not_moved(tmp_path: Path) -> None:
    snapshots_dir = tmp_path / "snapshots"
    snapshot.build_snapshot(FIXTURE_ROOT, snapshots_dir)
    live = LiveEngine(snapshots_dir, autostart=False)

    assert live.refresh() is False


def test_refresh_swaps_to_a_newly_published_snapshot(tmp_path: Path) -> None:
    snapshots_dir = tmp_path / "snapshots"
    snapshot.build_snapshot(FIXTURE_ROOT, snapshots_dir)
    live = LiveEngine(snapshots_dir, autostart=False)
    assert live.get_best_k_completions("brand new data source") == []

    second_root = _make_second_corpus(tmp_path)
    snapshot.build_snapshot(second_root, snapshots_dir)
    swapped = live.refresh()

    assert swapped is True
    results = live.get_best_k_completions("brand new data source")
    assert [r.completed_sentence for r in results] == ["A brand new data source arrived."]


def test_in_flight_reference_keeps_serving_the_old_snapshot_after_a_swap(
    tmp_path: Path,
) -> None:
    """A caller that grabbed `live.engine` before the swap must keep getting
    old-snapshot answers from that reference — the swap replaces which engine
    `live` points at, it never mutates the old engine in place. This is what
    "in-flight requests keep being served by the old snapshot" means for a
    reference-swap design: nothing already holding the old reference is
    disturbed by a later swap."""
    snapshots_dir = tmp_path / "snapshots"
    snapshot.build_snapshot(FIXTURE_ROOT, snapshots_dir)
    live = LiveEngine(snapshots_dir, autostart=False)
    in_flight_engine = live.engine

    second_root = _make_second_corpus(tmp_path)
    snapshot.build_snapshot(second_root, snapshots_dir)
    live.refresh()

    assert in_flight_engine is not live.engine
    assert in_flight_engine.get_best_k_completions("brand new data source") == []
    assert live.get_best_k_completions("brand new data source")


def test_start_and_stop_run_a_background_poller_that_picks_up_a_new_snapshot(
    tmp_path: Path,
) -> None:
    snapshots_dir = tmp_path / "snapshots"
    snapshot.build_snapshot(FIXTURE_ROOT, snapshots_dir)
    live = LiveEngine(snapshots_dir, poll_interval=0.02, autostart=False)
    live.start()
    try:
        second_root = _make_second_corpus(tmp_path)
        snapshot.build_snapshot(second_root, snapshots_dir)

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if live.get_best_k_completions("brand new data source"):
                break
            time.sleep(0.02)

        assert live.get_best_k_completions("brand new data source")
    finally:
        live.stop()


def test_stop_is_safe_to_call_when_never_started(tmp_path: Path) -> None:
    live = LiveEngine(tmp_path / "snapshots", autostart=False)

    live.stop()  # must not raise
