# EEL — Autocomplete

Fuzzy autocomplete over a 121 MB / 3.45 M-line text corpus, with an interactive
CLI. Google Project 2026, Part A.

**Read `SPEC.md` first**, then your own spec in `specs/`.

## Status

M0 complete — interfaces frozen. Every module below is a stub that raises
`NotImplementedError` except `src/models.py`, which is fully implemented because
it *is* the shared contract.

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
