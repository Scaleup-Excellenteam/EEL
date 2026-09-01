# Developer 3 — Monjed · Online / Search

**Branch:** `feature/online-search`
**Files you own:** `src/autocomplete.py`, `src/cli.py`, `main.py`, `tests/test_autocomplete.py`, `tests/test_cli.py`
**Files you must not touch:** `src/normalizer.py`, `src/scorer.py` (Elav) · `src/loader.py`, `src/index.py` (Qusai)
**Depends on:** the Elav and Qusai **interfaces**, not their code. You work against M0 stubs from hour one.
**Shared spec:** [`../SPEC.md`](../SPEC.md)

---

## 1. Your mission

You own the online stage — the part the grader actually sees and times. You take
Elav's score ladder and Qusai's substring index and assemble them into the
answer, then wrap it in the interactive loop the assignment specifies.

You are never blocked. `score_ladder` and `find_lines_containing` are both fully
specified at M0; build against the stubs and your code works unchanged when the
real implementations land.

You do not implement file loading, indexing, or the score formulas.

> Note: the old two-developer spec gave you `src/matcher.py` to test one
> substitution / insertion / deletion against candidate sentences. **That file is
> gone.** The score ladder removes that work entirely — variants arrive already
> corrected, so matching is a plain substring test.

---

## 2. What you are assembling — read before writing code

The score depends **only** on the query length and the edit's type and position —
never on which sentence matched. So the achievable scores form a fixed ladder,
and `score_ladder` yields it top-down as groups of *already-corrected* query
variants.

Your job: for each group, find the lines containing those variants as **exact
substrings**, in order, and stop the moment you hold 5 results. The first 5
distinct lines found this way are provably the top 5.

**You never compute an edit distance.** If you find yourself writing one, the
design has been misread.

---

## 3. `src/autocomplete.py`

```python
class AutoCompleteEngine:
    def __init__(self, corpus: Corpus, index: InvertedIndex): ...
    def get_best_k_completions(self, prefix: str, k: int = 5) -> list[AutoCompleteData]: ...
```

Keep `get_best_k_completions` exactly — it is the name the assignment mandates,
including the misleading `prefix`. The match is a substring anywhere in the
sentence, not a prefix.

### What you return

```python
@dataclass(frozen=True)
class AutoCompleteData:
    completed_sentence: str   # ORIGINAL line — punctuation and casing preserved
    source_text: str          # file path relative to the corpus root
    offset: int               # 1-based LINE NUMBER within the file
    score: int
```

**Exactly these four fields — never add one.** The assignment's stub ends with
`# methods that you need to define by yourself`: it invites *methods*, not extra
fields. `sort_key` and `__str__` are the only extension, and both are computable
from the four fields alone.

`completed_sentence` is the **original** line, not the normalized one. Users
search in a normalized world but must be shown the real text — the assignment is
explicit that output is "שורה מתוך קבצי המקור בצורתו המקורית", a line from the
source files in its original form.

### The algorithm

```
normalized = normalize(prefix)
results = []            # ordered
seen = set()            # line IDs already emitted

for group in score_ladder(normalized, corpus.alphabet):
    # each variant yields its OWN ascending stream — merge, do not concatenate
    streams = [index.find_lines_containing(v.text) for v in group]
    for line_id in heapq.merge(*streams):
        if line_id in seen:
            continue
        seen.add(line_id)
        results.append(build_result(line_id, group_score))
        if len(results) == k:
            return results

return results
```

### Three things to get right

**1. Merge within a tier — never sort.**
A single tier holds several variants (tier `2L−4` holds three different edit
kinds). Each variant yields its own ascending stream. The streams are
individually sorted but not *jointly* sorted, so combine them with `heapq.merge`.
Concatenating and sorting would force every stream to be fully drained,
destroying the early termination the whole design rests on.

**2. Dedup by line ID, and a line keeps its first score.**
Because you walk tiers in descending score order, the first time you see a line
is at its best achievable score. So check `seen` *before* appending, and skip a
line already in it — never re-score.

Dedup by **line ID, not by text**. The same sentence in two different files is
two distinct lines and may legitimately occupy two result slots — that is
`SPEC.md` §7.3, and it is why the assignment requires the file path in the
output.

**3. The tie-break is free — do not re-implement it.**
Qusai assigns line IDs in ascending `(normalized_sentence, source_text,
offset)` order, which is exactly `AutoCompleteData.sort_key` minus the score. So
ascending line IDs *are* the required alphabetical order. Combined with
`heapq.merge`, results arrive already correctly ordered — appending in arrival
order is correct.

Adding your own sort would be redundant work that also breaks laziness. If you
ever feel the need to sort, the ordering contract has been violated upstream;
raise it with Qusai rather than papering over it in `autocomplete.py`.

---

## 4. `src/cli.py` — the online loop

Required behaviour:

- Print a readiness banner once the offline stage completes:
  `The system is ready. Enter your text:`
- The user types and presses Enter → print the 5 best completions, numbered.
- **The typed text accumulates.** After showing completions the user continues
  typing *from where they stopped* — the next Enter appends to the query rather
  than replacing it. Echo the accumulated text so the user can see their position.
- `#` means the user is done with this sentence: clear the accumulated text and
  return to the initial state.

Output format, per the assignment's sample:

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

Reproduce this exactly — it is the clearest statement of expected output in the
assignment, and the obvious thing for a grader to eyeball first. (`this is` is 7
normalized characters, so an exact match scores `2×7 = 14`, which is a useful
sanity check that your wiring is right.)

### Edge cases to handle

- Empty input (bare Enter) — do not crash, do not search.
- Fewer than 5 matches — print what exists, do not pad.
- No matches at all — say so plainly.
- `#` typed mid-word, and `#` typed when the query is already empty.
- Whitespace-only input.

---

## 5. `main.py`

The single entry point: run the offline stage (load corpus, build the index),
print the readiness banner, then hand control to the CLI loop. This is what the
grader runs.

Keep it thin — wiring only, no logic. Anything worth testing belongs in
`autocomplete.py` or `cli.py`.

---

## 6. Testing against stubs

You do not need Elav's or Qusai's real code. Write fakes in your own test files:

- a fake index whose `find_lines_containing` returns canned ascending generators,
  so you can assert merge behaviour and early termination precisely;
- a fake `score_ladder` yielding a known tier sequence, so you can assert dedup
  and stop conditions without depending on real scoring.

This is not a workaround for the others being unfinished. Testing your
orchestration against fakes is genuinely better, because it lets you construct
tier and stream shapes a real corpus would rarely produce.

### The tests that matter most

- **Early termination.** Assert `find_lines_containing` is *not* called for any
  tier below the one that filled the result list. This is the single most
  valuable test in your track — it is what protects half the project grade.
- **Merge correctness.** A tier with several variants whose streams interleave
  returns results in ascending line-ID order.
- **Laziness.** A fake stream that raises on its Nth item proves you never
  consumed past what you needed.
- **Dedup.** A line reachable from two different tiers appears once, with the
  higher score.
- **End-to-end.** The assignment's `example.txt` scenario reproduces exactly,
  character for character.
- **CLI state.** Text accumulates across Enter presses; `#` clears it.

---

## 7. Definition of done

- [ ] `get_best_k_completions` keeps the assignment's exact signature
- [ ] Tiers walked in descending order, with `heapq.merge` within each tier
- [ ] Dedup by line ID, first-seen score kept
- [ ] Early termination proven by test
- [ ] Laziness proven by test
- [ ] No sorting of results, and no edit-distance computation anywhere
- [ ] `completed_sentence` returns the original line, not the normalized one
- [ ] `example.txt` scenario reproduces exactly
- [ ] All §4 edge cases covered
- [ ] No imports from `loader.py`'s or `index.py`'s internals — interfaces only
