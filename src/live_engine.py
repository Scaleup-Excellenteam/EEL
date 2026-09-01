"""LiveEngine: the online half of ZDT's hand-off (see src/snapshot.py).

Wraps whichever `AutoCompleteEngine` is built from the snapshot currently
published under `snapshots_dir`, and hot-swaps to a new one when a later
offline build publishes a newer snapshot -- no restart, and no query blocks
on the swap.

Duck-types `AutoCompleteEngine.get_best_k_completions(prefix, k=...)`, which
is the only method `src/cli.run` calls on its `engine` argument, so a
`LiveEngine` drops straight into that existing, unmodified loop -- see
src/serve.py.
"""

from __future__ import annotations

import threading

from src.autocomplete import AutoCompleteEngine, DEFAULT_K
from src.models import AutoCompleteData
from src.snapshot import current_version_dir, load_current


class LiveEngine:
    """Serves queries from the current snapshot, reloading it as it changes.

    Reads and writes of `self._engine` are plain attribute access, which
    CPython guarantees is atomic under the GIL: a query either sees the
    engine from before a swap or the one from after, in full, never a
    half-built one. That is what lets `refresh` (called from a background
    poll thread, or directly in tests) replace the active engine while
    `get_best_k_completions` keeps answering concurrently on the old one,
    with no lock needed on the read path.
    """

    def __init__(
        self,
        snapshots_dir,
        *,
        poll_interval: float = 1.0,
        autostart: bool = True,
    ) -> None:
        self._snapshots_dir = snapshots_dir
        self._poll_interval = poll_interval
        self._current_version_dir = None
        self._engine: AutoCompleteEngine | None = None
        self._stop_event = threading.Event()
        self._poll_thread: threading.Thread | None = None

        self.refresh()
        if autostart:
            self.start()

    @property
    def engine(self) -> AutoCompleteEngine | None:
        """The `AutoCompleteEngine` currently in use, or None if no snapshot
        has ever been published under `snapshots_dir`."""
        return self._engine

    def get_best_k_completions(
        self, prefix: str, k: int = DEFAULT_K
    ) -> list[AutoCompleteData]:
        """Delegate to the currently active engine.

        Raises if no snapshot has ever been published — callers (see
        src/serve.py) are expected to check `.engine is not None` at startup
        rather than let every query fail one at a time.
        """
        if self._engine is None:
            raise RuntimeError(
                f"no snapshot published yet under {self._snapshots_dir}"
            )
        return self._engine.get_best_k_completions(prefix, k)

    def refresh(self) -> bool:
        """Reload from `current` if it points somewhere new. Returns whether
        a swap happened.

        Safe to call from any thread: it only ever replaces `self._engine`
        with a fully-built new one, never mutates an engine already in use.
        """
        version_dir = current_version_dir(self._snapshots_dir)
        if version_dir is None or version_dir == self._current_version_dir:
            return False

        index = load_current(self._snapshots_dir)
        self._engine = AutoCompleteEngine(index.corpus, index)
        self._current_version_dir = version_dir
        return True

    def start(self) -> None:
        """Start polling `current` for a new snapshot in the background."""
        if self._poll_thread is not None:
            return
        self._stop_event.clear()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def stop(self) -> None:
        """Stop the background poll, if running. Safe to call repeatedly."""
        if self._poll_thread is None:
            return
        self._stop_event.set()
        self._poll_thread.join()
        self._poll_thread = None

    def _poll_loop(self) -> None:
        while not self._stop_event.wait(self._poll_interval):
            self.refresh()
