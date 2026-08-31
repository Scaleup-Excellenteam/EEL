# EEL Autocomplete Project — Specification

**Team:** Elav, Qusai, Monjed
**Assignment:** Google Project 2026, Part A — "Automatic Sentence Completion"
**Source of truth:** `google_project_2026_part_a.docx` + `Archive.zip`

> This replaces the earlier two-developer `SPEC.md` (commit `95103d2`), which was
> cleared by "Reset project for three-person team". Two things changed beyond
> adding a third developer, and both are called out where they occur:
> the normalizer moved from the offline developer to the scoring developer, and
> `src/matcher.py` is gone — see §5.
>
> Each developer also has a standalone spec in `specs/` with their own pitfalls
> and checklist. Read this file first, then yours.

---

## 1. Project Goal

Build an autocomplete system that searches a collection of text files and returns
the 5 best matching sentences for text entered by the user.

The system must support:

- Exact substring matching — anywhere in the sentence, not only at the start
- Maximum one character error: substitution, insertion, or deletion
- Case-insensitive matching
- Ignoring punctuation during matching
- Collapsing repeated spaces
- Scoring according to the assignment rules
- Returning the best 5 matches
- Alphabetical ordering when scores are equal

Implemented in Python. The assignment requires the completion function to be
Python and permits any language for initialization; we use Python for both so the
team maintains one codebase and one test suite.

Graded on two metrics only: **correctness** and **speed**.

### The corpus (measured from `Archive.zip`)

| Property | Value |
|---|---|
| Text files | 1,504 (`.txt` only) |
| Directories | 14, nesting up to 3 levels deep |
| Total size | ~121 MB |
| Total lines | ~3,450,000 |
| Content | English technical documentation, with punctuation |
| Sentence | one full line in a file |

---

## 2. Scoring rules

All scoring is on **normalized** text: lowercase, punctuation removed, runs of
whitespace collapsed to a single space. Spaces count as characters. Positions are
1-based **in the normalized query**. `L` = normalized query length.

| Penalty position | 1 | 2 | 3 | 4 | 5+ |
|---|---|---|---|---|---|
| Substitution | 5 | 4 | 3 | 2 | 1 |
| Insert / delete | 10 | 8 | 6 | 4 | 2 |

`score = 2 × (matching characters) − penalty`

| Case | Matching chars | Score |
|---|---|---|
| Exact substring | L | `2L` |
| Substitution at position *i* | L − 1 | `2(L−1) − sub(i)` |
| Query has an **extra** char at *i* (delete it) | L − 1 | `2(L−1) − indel(i)` |
| Query is **missing** a char at *i* (insert it) | L | `2L − indel(i)` |

Note the asymmetry. A **missing** character still earns full matching points for
every character the user actually typed; only the inserted character earns
nothing. An **extra** character costs one matching point *as well as* the
penalty. This is the easiest thing in the project to get wrong.

All four formulas were verified against all twelve worked examples in the
assignment — the seven in the English appendix and the five in the Hebrew body.

---

## 3. The key insight — read before writing any code

> **The score depends only on the query length and the edit's type and position.
> It does not depend on which sentence matched.**

So the achievable scores form a **fixed ladder of 10 tiers**, fully known before
touching the corpus:

```
2L      exact match
2L−2    missing char at position ≥5
2L−3    substitution at position ≥5
2L−4    missing char at 4  |  substitution at 4  |  extra char at ≥5
2L−5    substitution at 3
2L−6    missing char at 3  |  substitution at 2  |  extra char at 4
2L−7    substitution at 1
2L−8    missing char at 2  |  extra char at 3
2L−10   missing char at 1  |  extra char at 2
2L−12   extra char at 1
```

**Consequence: we never perform fuzzy matching, and never compute an edit
distance.** We walk the ladder top-down. At each tier we generate the
already-corrected query variants and search for each as an **exact substring**.
The first 5 distinct lines collected are provably the answer, and we stop there.
Most queries never leave tier 1 or 2.

A naive implementation — loop over 3.45 M lines, run edit distance on each —
takes seconds to minutes per query. Speed is half the grade. The ladder is how
we win it.

The whole project therefore reduces to one primitive:

> **Given an exact string, find the lines containing it — fast.**

---

## 4. Architecture

### Offline

Text files → load sentences → normalize → build inverted index → ready to serve

### Online

User query → normalize → walk the score ladder → for each variant, exact
substring lookup → dedup → return best 5

### The index

A word-level inverted index: `word → sorted list of line IDs containing it`.
Roughly 20 M word occurrences as `array('i')` ≈ 80 MB RAM.

To find lines containing a pattern, take the pattern's **rarest interior word**,
walk its posting list, and verify each candidate with a direct substring check.
Instead of scanning 3.45 M lines we scan a few hundred. The index narrows
candidates; verification decides matches.

**Only strictly interior words are safe to look up.** In the pattern `or no`, the
trailing `no` may be part of `not` and the leading `or` may be part of `for`.
Edge tokens are fragments, not words. A token is strictly interior when it has a
space on both sides *within the pattern*. Patterns with no interior token use the
fallback in `specs/qusai-offline-index.md` §5.4.

---

## 5. Shared Models

All three developers use the same models. `src/models.py` is written first,
together, and then frozen.

```python
@dataclass(frozen=True)
class SentenceData:
    original_sentence: str     # the line exactly as it appears in the file
    normalized_sentence: str   # normalize(original_sentence)
    source_text: str           # file path relative to the corpus root
    offset: int                # 1-based line number within the file


@dataclass(frozen=True)
class AutoCompleteData:
    completed_sentence: str    # ORIGINAL line — punctuation and casing preserved
    source_text: str           # file path relative to the corpus root
    offset: int                # 1-based line number within the file
    score: int

    def sort_key(self) -> tuple[int, str, str, int]:
        """(-score, completed_sentence.casefold(), source_text, offset)"""

    def __str__(self) -> str:
        """'<sentence> (<source>:<offset>, score=<score>)'"""
```

`AutoCompleteData` carries **exactly these four fields — never add one.** The
assignment's stub ends with `# methods that you need to define by yourself`: it
invites *methods*, not extra fields. `sort_key` and `__str__` are the whole
extension, and both are computable from the four fields alone.

`sort_key` is a method rather than `order=True` because dataclass ordering
compares fields in declaration order, which is wrong here.

Required public function:

```python
get_best_k_completions(prefix: str) -> List[AutoCompleteData]
```

Keep this name exactly, including the misleading `prefix` — the match is a
substring anywhere in the sentence.

### Module ownership

| Module | Owner |
|---|---|
| `src/models.py` | all three, at M0, then frozen |
| `src/normalizer.py` | Elav |
| `src/scorer.py` | Elav |
| `src/loader.py` | Qusai |
| `src/index.py` | Qusai |
| `src/autocomplete.py` | Monjed |
| `src/cli.py` | Monjed |
| `main.py` | Monjed |

**Two changes from the two-developer spec.** First, `src/normalizer.py` moved
from the offline developer to Elav: normalization is a scoring concern, it is
what defines "matching characters", and it belongs beside the score formulas that
depend on it. Second, **`src/matcher.py` no longer exists.** The two-developer
spec needed it to test "one substitution / one insertion / one deletion" against
candidate sentences. The score ladder (§3) removes that work entirely — variants
arrive already corrected, so matching is a plain substring test. If you find
yourself writing a matcher, the design has been misread.

---

## 6. Integration Contract

```
Qusai  ──SentenceData + line IDs──▶  Monjed  ──AutoCompleteData──▶  user
                                        ▲
Elav   ──normalize() + score_ladder()───┘
```

- **Qusai → Monjed:** `loader` and `index` expose sentences by line ID, and
  `index.find_lines_containing(pattern)` yields line IDs.
- **Elav → Monjed:** `normalizer.normalize()` and `scorer.score_ladder()`.
- **Elav → Qusai:** `normalizer.normalize()` only.

Do not create duplicate implementations of `SentenceData`, `AutoCompleteData`, or
normalization. Shared interfaces must not be changed without agreement between
all three developers.

### The line-ID ordering contract

> **Line IDs are assigned in ascending order of
> `(original_sentence.casefold(), source_text, offset)`** — the same key as
> `AutoCompleteData.sort_key` minus the score.

Every posting list, sorted by line ID, is then *already* in the required
tie-break order. This makes the alphabetical tie-break free and makes lazy early
termination **legal** — Monjed can stop at the 5th hit instead of collecting
every hit and sorting.

This is the single highest-risk line in the project. If Qusai's key and
`sort_key` disagree, results come back mis-ordered with no exception and no
failing assertion — just quietly wrong output. It must be asserted by an
explicit test on both sides.

`find_lines_containing` must also be **lazy** and yield in **ascending** order.
A version that builds and returns a list is correct but slow, and speed is half
the grade.

---

## 7. Decisions

Settled, with the evidence, so they can be challenged against the assignment
rather than against opinion.

**7.1 `offset` is a 1-based line number.** The assignment names the field
"מיקום/שורה" — position/line — and its sample output prints `example.txt:1` …
`example.txt:5` for a five-line file.

**7.2 Tie-break key is `(-score, completed_sentence.casefold(), source_text,
offset)`.** The assignment says equal scores sort alphabetically without naming
which form of the text. We sort by the **displayed** sentence, case-folded:
sorting by what is printed is the only reading a grader can verify by eye;
`casefold()` avoids the ASCII artifact where `"Zebra" < "apple"`; and
`source_text` then `offset` make the order total, so output is deterministic.

**7.3 Dedup by line ID, not by text.** A single corpus line must never occupy two
result slots. An identical sentence in two *different* files is two distinct
lines and may legitimately occupy two slots — the assignment requires the file
path in the output precisely because the same text can live in more than one
place.

**7.4 Offline build runs in-process, with persistence behind a flag.** The
assignment describes one program in two stages and prints its readiness banner
after the build, so the build is user-visible. Revisit at M3 **with a measured
build time in hand**: if it takes minutes, persistence becomes the default.

**7.5 Non-positive scores are filtered.** A score of zero or below means zero
matching characters — nothing the user typed actually matched. The assignment
never reaches this case; the filter only prevents pathological queries from
returning negative-scored garbage.

**7.6 External libraries are permitted** — the assignment forbids none. But the
core algorithm is ours, because the assignment also requires each of us to be
able to explain precisely how the solution works.

---

## 8. Developer 1 — Elav · Scoring Core

**Branch:** `feature/scoring-core` · **Spec:** `specs/elav-scoring-core.md`
**Also:** integration owner

Owns `src/normalizer.py`, `src/scorer.py`, and a test-only reference
implementation. Delivers normalization, the four score formulas, and
`score_ladder` — the generator that makes the whole design work.

Depends on nothing. Pure functions, testable without a corpus, an index, or a
CLI. **Must land first**, because it is the correctness oracle everything else is
verified against.

Elav does not implement file loading, indexing, or the CLI.

---

## 9. Developer 2 — Qusai · Offline / Data

**Branch:** `feature/offline-index` · **Spec:** `specs/qusai-offline-index.md`

Owns `src/loader.py` and `src/index.py`. Delivers the recursive file walk,
`SentenceData` records, the line-ID ordering contract, the inverted index,
`find_lines_containing`, and `save`/`load`.

Depends on `normalizer.normalize` only — available as a stub from M0.

**Ship the slow version first.** At M1, `find_lines_containing` may be a plain
brute-force scan. It is correct, it satisfies the interface, and it unblocks
Monjed on day one. The real index replaces it at M3 with zero changes to any
other file. Make it work, then make it fast.

Qusai does not implement scoring or final ranking.

---

## 10. Developer 3 — Monjed · Online / Search

**Branch:** `feature/online-search` · **Spec:** `specs/monjed-online-search.md`

Owns `src/autocomplete.py`, `src/cli.py`, and `main.py`. Delivers the ladder
walk with early termination, the per-tier k-way merge, dedup by line ID, the
interactive loop, accumulating typed text, the `#` reset, and output formatting.

Depends on the Elav and Qusai **interfaces**, not their code — works against M0
stubs from hour one, so is never blocked.

Monjed does not implement file loading, indexing, or the score formulas.

---

## 11. Required CLI behaviour

- Print a readiness banner once the offline stage completes:
  `The system is ready. Enter your text:`
- User types, presses Enter → print the 5 best completions, numbered.
- **The typed text accumulates.** After showing completions the user continues
  typing from where they stopped; the next Enter appends rather than replaces.
  Echo the accumulated text.
- `#` means the user finished this sentence: clear the text, return to the
  initial state.

Output format, per the assignment's own sample:

```
The system is ready. Enter your text:
this is
Here are 5 suggestions:
1. Alpha: this is a demo. (example.txt:1, score=14)
2. Beta: this is a demo. (example.txt:2, score=14)
3. Delta: this is a demo. (example.txt:3, score=14)
4. Gamma: this is a demo. (example.txt:4, score=14)
5. Omega: this is a demo. (example.txt:5, score=14)
this is
```

Each line shows the **original** sentence with punctuation and casing intact, the
source path, the offset, and the score. Reproduce this exactly — it is the
clearest statement of expected output in the assignment, and the obvious thing
for a grader to check first.

---

## 12. Milestones

| # | Who | Deliverable | Gate |
|---|---|---|---|
| **M0** | all three | `src/models.py`, every signature as a stub, `pytest.ini`, `requirements.txt` | **Interfaces frozen.** Nothing else starts first. |
| **M1** | in parallel | Elav: formulas + ladder + tests. Qusai: loader + brute-force `find_lines_containing`. Monjed: ladder walk + CLI against stubs. | Three tracks running, nobody blocked |
| **M2** | Elav | End-to-end on the fixture corpus | **System works, slowly.** |
| **M3** | Qusai | Real inverted index, drop-in | **System works, fast.** |
| **M4** | all three | Full-corpus run, reference cross-check, latency measurements, README | Ready to submit |

M0 is short but non-negotiable — it is what buys the parallelism.

---

## 13. Git Rules

All three developers start from the same `main`.

Do not work directly on `main` after branches are created. Each developer works
only on their own branch:

| Developer | Branch |
|---|---|
| Elav | `feature/scoring-core` |
| Qusai | `feature/offline-index` |
| Monjed | `feature/online-search` |

**File ownership is exclusive.** Do not edit files owned by another developer
without agreement. The module boundaries in §5 are chosen so that merge
conflicts are structurally impossible.

Before merging:

1. Commit all work.
2. Pull latest `main`.
3. Merge `main` into the feature branch if necessary.
4. Run tests.
5. Open the pull request.

---

## 14. Definition of Done

- All 1,504 corpus files load correctly, at every folder depth
- Exact substring matching works, anywhere in the sentence
- Case-insensitive matching works
- Punctuation is ignored during matching
- Repeated spaces are collapsed
- One substitution, one insertion, one deletion each work
- More than one edit is rejected
- Scores follow the assignment rules — all twelve worked examples pass as tests
- The best 5 results are returned
- Equal scores are sorted alphabetically, deterministically
- The original sentence is returned in its original form
- Source file path and 1-based line number are returned
- The line-ID ordering contract is asserted by a test on both sides
- Early termination is proven by a test
- The interactive program works, including text accumulation and `#`
- Query latency on the full 121 MB corpus is measured and recorded in the README
- All three developers understand the complete solution
