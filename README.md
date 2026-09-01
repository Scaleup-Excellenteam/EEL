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
| tests | 256 passing |

Deferred by decision, not omission: `InvertedIndex.save`/`load` — persistence is
behind a flag per `SPEC.md` §7.4, revisited at M3 now that the build time is
measured at 21 s.

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

## Layout and ownership

| Path | Owner | Branch |
|---|---|---|
| `src/models.py` | all three, frozen at M0 | — |
| `src/normalizer.py`, `src/scorer.py` | Elav | `feature/scoring-core` |
| `src/loader.py`, `src/index.py` | Qusai | `feature/offline-index` |
| `src/autocomplete.py`, `src/cli.py`, `main.py` | Monjed | `feature/online-search` |

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
