"""Tests for the ZDT entry-point scripts: build_snapshot.py and serve.py.

Mirrors tests/test_cli.py::test_main_loads_builds_creates_engine_and_runs_cli
-- monkeypatch the collaborators an entry point's `main` wires together and
assert on the call sequence, the same convention main.py's own test uses.
"""

from pathlib import Path

import build_snapshot as build_snapshot_module
import serve as serve_module


def test_build_snapshot_main_uses_given_paths_and_reports_the_published_version(
    monkeypatch, capsys
):
    calls = []
    published = Path("snapshots/20260101T000000000000Z-deadbeef")

    def fake_build_snapshot(corpus_root, snapshots_dir):
        calls.append((corpus_root, snapshots_dir))
        return published

    monkeypatch.setattr(build_snapshot_module, "build_snapshot", fake_build_snapshot)

    exit_code = build_snapshot_module.main(["custom-corpus", "custom-snapshots"])

    assert exit_code == 0
    assert calls == [(Path("custom-corpus"), Path("custom-snapshots"))]
    assert published.name in capsys.readouterr().out


def test_build_snapshot_main_falls_back_to_default_paths(monkeypatch):
    calls = []

    def fake_build_snapshot(corpus_root, snapshots_dir):
        calls.append((corpus_root, snapshots_dir))
        return Path("snapshots/version")

    monkeypatch.setattr(build_snapshot_module, "build_snapshot", fake_build_snapshot)

    exit_code = build_snapshot_module.main([])

    assert exit_code == 0
    assert calls == [
        (
            build_snapshot_module.DEFAULT_CORPUS_ROOT,
            build_snapshot_module.DEFAULT_SNAPSHOTS_DIR,
        )
    ]


def test_serve_main_reports_and_exits_nonzero_when_no_snapshot_published(
    tmp_path,
):
    exit_code = serve_module.main([str(tmp_path / "empty-snapshots")])

    assert exit_code == 1


def test_serve_main_runs_cli_against_a_live_engine_and_always_stops_it(
    monkeypatch, tmp_path
):
    calls = []

    class FakeLiveEngine:
        def __init__(self, snapshots_dir):
            calls.append(("init", snapshots_dir))
            self.engine = object()

        def stop(self):
            calls.append(("stop",))

    def fake_run(engine):
        calls.append(("run", engine))
        raise RuntimeError("boom")  # run() must not prevent stop() from firing

    monkeypatch.setattr(serve_module, "LiveEngine", FakeLiveEngine)
    monkeypatch.setattr(serve_module, "run", fake_run)

    try:
        serve_module.main([str(tmp_path)])
    except RuntimeError:
        pass

    assert calls[0] == ("init", tmp_path)
    assert calls[1][0] == "run"
    assert calls[2] == ("stop",)
