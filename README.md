# EEL — Autocomplete

Fuzzy autocomplete over a 121 MB / 3.45 M-line text corpus, with an interactive
CLI. Google Project 2026, Part A.

**Read `SPEC.md` first**, then your own spec in `specs/`.

## Status

**M1 complete and integrated.** All three tracks are implemented and merged; the
system runs end to end on the full 121 MB corpus and reproduces the assignment's
sample output byte for byte.

Measured on the real corpus (2,391,950 sentences after empty lines are excluded):

| | |
|---|---|
| offline (load + index) | **21 s**, ~1.2 GB RSS |
| query latency, typical | **under 1 ms** |
| query latency, worst of 12 | **137 ms** |
| tests | 340 passing |

`InvertedIndex.save`/`load` were deferred behind a flag per `SPEC.md` §7.4,
pending a measured build time. That's in hand now (21 s below), and ZDT (next
section) is the revisit: persistence is implemented and is the filesystem
hand-off the offline and online stages use instead of sharing memory.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
```

The corpus is not in the repo (see `.gitignore`). Unzip `Archive.zip` to
`./Archive` before running `main.py`.

```bash
python main.py            # uses ./Archive
python main.py some/path  # or point it elsewhere
```

`main.py` is the original M1 path: it builds the index in-process, in memory,
every time it starts. For zero-downtime operation instead, see ZDT below.

## ZDT: Zero DownTime

`main.py` couples offline indexing to the online process: adding new corpus
data means restarting it. ZDT decouples them through the filesystem, so a new
data source can be added to a running service without ever stopping it.

```bash
python build_snapshot.py            # offline: uses ./Archive -> ./snapshots
python build_snapshot.py some/corpus some/snapshots  # or point it elsewhere

python serve.py                     # online: serves from ./snapshots, live
python serve.py some/snapshots      # or point it elsewhere
```

**How the hand-off works** (`src/snapshot.py`):

1. `build_snapshot.py` loads a corpus and builds an index exactly as `main.py`
   does, but instead of holding it in memory it writes it — via
   `InvertedIndex.save`, now a real implementation, not the M1 stub — to its
   own fresh, uniquely named directory under `snapshots/`. An existing
   snapshot is never overwritten in place.
2. It loads that file straight back to confirm it actually works, and only
   then repoints `snapshots/current` at the new directory — one atomic
   symlink rename (`os.replace`), so a reader of `current` always sees either
   the previous snapshot in full or the new one in full, never a partial one.
3. `serve.py` loads whichever snapshot `current` names at startup and hands
   it to the same interactive CLI `main.py` uses (`src/cli.run`), through
   `LiveEngine` (`src/live_engine.py`), which polls `current` in the
   background (every second by default) and hot-swaps to a newer snapshot the
   moment one is published — no restart. A query already in flight keeps
   using the engine reference it already has; only the next query sees the
   new data.

**Adding a data source with zero downtime**, concretely: with `serve.py`
already running, drop the new files into (or alongside) the corpus root and
run `build_snapshot.py` again — from the same machine, or from anywhere else
if `snapshots/` is a shared/network mount — no restart, and no interruption
to whatever query is already in flight in `serve.py`.

## Layout and ownership

| Path | Owner | Branch |
|---|---|---|
| `src/models.py` | all three, frozen at M0 | — |
| `src/normalizer.py`, `src/scorer.py` | Elav | `feature/scoring-core` |
| `src/loader.py`, `src/index.py` | Qusai | `feature/offline-index` |
| `src/autocomplete.py`, `src/cli.py`, `main.py` | Monjed | `feature/online-search` |
| `src/snapshot.py`, `src/live_engine.py`, `build_snapshot.py`, `serve.py` | ZDT initiative | `cat/zdt-zero-downtime` |

**File ownership is exclusive.** Do not edit another developer's files without
agreement — the boundaries are chosen so merge conflicts are structurally
impossible. Full rules in `SPEC.md` section 13.

## Tests

`tests/test_interfaces.py` is the M0 freeze: it asserts every module imports,
every agreed signature exists with the agreed parameter names, and every stub
raises rather than silently returning `None`. If it fails after M0, a shared
interface changed without the three-way agreement `SPEC.md` section 6 requires.

Add your own test files as you go; they are yours, same as your modules.

## The one thing to understand before coding

The score depends only on the query length and on which edit was made where —
never on which sentence matched. So the possible scores form a fixed ladder of
ten tiers, and we walk it top-down doing **exact substring searches** on
already-corrected query variants, stopping at the fifth hit.

No edit distance is ever computed. `SPEC.md` section 3 explains why.
