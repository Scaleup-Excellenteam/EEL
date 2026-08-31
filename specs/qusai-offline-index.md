# Developer 2 — Qusai · Offline / Data

**Branch:** `feature/offline-index`
**Files you own:** `src/loader.py`, `src/index.py`, `scripts/build_index.py`, `tests/test_loader.py`, `tests/test_index.py`, `tests/fixtures/`
**Files you must not touch:** `src/normalizer.py`, `src/scorer.py` (Elav) · `src/autocomplete.py`, `src/cli.py`, `main.py` (Monjed)
**Depends on:** `normalizer.normalize` only — available as a stub from M0
**Shared spec:** [`../SPEC.md`](../SPEC.md)

---

## 1. Your mission

You own the offline stage and the single primitive the entire system reduces to:

> **Given an exact string, find the lines containing it — fast.**

Half the project grade is speed, and essentially all of the achievable speed
lives in your track. This is the heaviest engineering on the team and it is fully
independent of the other two.

You do not implement scoring or final ranking. You also do not own
`src/normalizer.py` — that moved to Elav, because normalization is what defines
"matching characters". You import it.

---

## 2. The corpus you are indexing (measured)

| Property | Value |
|---|---|
| Text files | 1,504 (`.txt` only — no other file types present) |
| Directories | 14, nesting up to 3 levels deep |
| Total size | ~121 MB |
| Total lines | ~3,450,000 |
| Content | English technical docs (Python docs, pandas, nginx, PostgreSQL, Perl, PyTorch) |
| Sentence | one full line in a file |

Files sit at varying depths — a file may be at the root or nested three levels
down. Walk recursively; never assume a flat layout.

---

## 3. Ship the slow version first

**At M1, `find_lines_containing` may be a plain brute-force scan over all
lines.** It is correct, it satisfies the interface, and it unblocks Monjed on day
one. The real inverted index drops in at M3 with **zero changes to any other
file**.

Make it work, then make it fast. Do not build the fast index before the slow one
passes tests — you would have no oracle to check it against.

---

## 4. `src/loader.py`

```python
@dataclass(frozen=True)
class SentenceData:
    original_sentence: str     # the line exactly as it appears in the file
    normalized_sentence: str   # normalize(original_sentence)
    source_text: str           # path relative to the corpus root
    offset: int                # 1-based line number (SPEC.md §7.1)

class Corpus:
    alphabet: str              # every distinct char observed after normalization

    @classmethod
    def load(cls, root: Path) -> "Corpus": ...
    def __len__(self) -> int: ...
    def __getitem__(self, line_id: int) -> SentenceData: ...
    def normalized(self, line_id: int) -> str: ...
```

### The line-ID ordering contract — the most important thing in your track

> **Line IDs are assigned in ascending order of
> `(normalized_sentence, source_text, offset)`.**

This is **the same key** as `AutoCompleteData.sort_key` minus the score. If your
key and `sort_key` disagree, your ordering and Monjed's ordering disagree and the
output comes back mis-ordered.

> ⚠️ **Corrected at the M1 integration merge.** This spec originally told you to
> key on `original_sentence.casefold()` — the raw line. That was wrong, and it
> was a correctness bug, not a cosmetic one. In ASCII, control chars < tab <
> space < punctuation < digits < letters, and **40% of the real corpus (964,432
> of 2,391,950 lines) starts with whitespace**. So indentation decided
> "alphabetical" order, and because the engine stops at the fifth hit,
> alphabetically earlier sentences were **dropped from the result set entirely**.
> Sort on `normalized_sentence` — the content — instead. See SPEC.md §7.2.

Every posting list, sorted by line ID, is then *already* in the required
tie-break order. This makes the alphabetical tie-break free and — critically —
makes Monjed's lazy early termination **legal**: he can stop at the 5th hit
instead of collecting every hit and sorting.

If you break this contract, his early termination silently returns wrong
answers — no exception, no failing assertion, just quietly wrong results. **This
is the single highest-risk line in the project. Assert it in a test.**

Including `source_text` and `offset` makes the order **total**, so results are
deterministic when the same sentence appears in two files.

Sorting 3.45 M strings is a real cost — expect tens of seconds. It is paid once,
offline, and it buys correctness plus early termination in the online stage.

### Other rules

- **Exclude** lines whose normalized form is empty — blank lines and
  punctuation-only lines. They cannot match any non-empty query.
- **Preserve `original_sentence` byte-for-byte.** The assignment requires output
  in the source's original form, punctuation included.
- **Derive `alphabet` from the actual corpus**, never hardcode `a–z`. Elav
  generates substitution and insertion variants from it; a wrong alphabet means
  missed matches.
- Decide and document the encoding policy. `utf-8` with `errors="replace"` is the
  safe default for 1,504 files you did not author.
- Storing 3.45 M dataclass instances is memory-hostile. Prefer parallel lists or
  a columnar layout internally and construct a `SentenceData` on demand in
  `__getitem__`.

---

## 5. `src/index.py`

```python
class InvertedIndex:
    @classmethod
    def build(cls, corpus: Corpus) -> "InvertedIndex": ...

    def find_lines_containing(self, pattern: str) -> Iterator[int]:
        """Yield line IDs whose normalized text contains `pattern` as a
        substring. MUST yield in ascending line-ID order. MUST be lazy — the
        caller stops early. `pattern` is already normalized."""

    def save(self, path: Path) -> None: ...
    @classmethod
    def load(cls, path: Path) -> "InvertedIndex": ...
```

`find_lines_containing` has two load-bearing properties. **Ascending order** is
what makes the tie-break correct. **Laziness** is what makes early termination
possible. A version that builds and returns a list is a correctness bug in
Monjed's code, not a performance nit — it will be correct but slow, and speed is
half the grade.

### 5.1 Structure: word-level inverted index

`word → sorted list of line IDs containing it`.

Sizing: ~20 M word occurrences as `array('i')` ≈ **80 MB RAM**. Comfortable.

A character 4-gram index would need ~480 MB of postings and build far more
slowly. It is the escape hatch in §5.4, not the plan.

Build hint: accumulate into per-word Python lists, then freeze into one flat
`array('i')` plus a `dict[str, tuple[int, int]]` of (start, end) slices. Per-word
`array` objects carry too much per-object overhead at ~500 K distinct words.

### 5.2 Query strategy: classify every token by its word boundary

1. Split `pattern` on spaces.
2. Classify each token by the spaces around it (§5.3) and get its candidate
   **word** set.
3. If any token's candidate set is **empty**, the pattern is unmatchable — return
   immediately. This is the strongest pruner you have.
4. Otherwise pick the token whose candidate words have the **fewest total
   postings**.
5. Walk those postings in ascending order, lazily, merging if there is more than
   one word.
6. Verify each candidate with `pattern in corpus.normalized(line_id)`.
7. Yield the line ID if it verifies.

Instead of scanning 2.39 M lines you scan a few hundred. Verification is what
makes this exact rather than approximate — the index narrows candidates, it does
not decide matches.

### 5.3 Every token sits at a known word boundary

The original version of this spec used only *strictly interior* tokens — those
with a space on both sides — and scanned the whole corpus when there were none.
That was sound but it was also the main path in practice, because a one- or
two-word pattern has no interior token at all:

```
'python'              interior tokens: []                -> FULL SCAN
'this is'             interior tokens: []                -> FULL SCAN
'import numpy'        interior tokens: []                -> FULL SCAN
'import numpy as np'  interior tokens: ['numpy', 'as']   -> index
```

Since the engine walks the score ladder, one mistyped two-word query produced
909 variants and ~90% of them each scanned all 2,391,950 lines. Measured:
`numpy arrray` did not finish in four minutes; `interpretor` took 129 s.

The fix is that interiority is not the only thing a space tells you. **Each of
the four boundary cases is soundly indexable:**

| Spaces around the token | The token is a word... | Lookup |
|---|---|---|
| both sides | **whole word** | dict hit |
| before only | **prefix** | bisect on sorted words |
| after only | **suffix** | bisect on sorted *reversed* words |
| neither | **infix** | `str.find` over a blob of the vocabulary |

A token is space-bounded on the left when it is not the first token, or the
pattern starts with a space; and on the right when it is not the last token, or
the pattern ends with a space.

So `numpy arrray` classifies as suffix(`numpy`) + prefix(`arrray`). No corpus
word starts with `arrray`, so the pattern is rejected in microseconds instead of
after a full scan. Worst case across a 12-query benchmark fell from *not
finishing* to **255 ms**.

### 5.4 The unsound shortcut — do not take it

This section previously said: *"if an edge token happens to be a complete corpus
word, use it anyway as a candidate source; it may over-generate candidates but
never under-generates."*

**That was wrong.** It under-generates, and silently:

```
line:    'bathis isnt here'      words = ['bathis', 'isnt', 'here']
pattern: 'this is'               IS a substring of that line
                                 but the line has NO word 'this'
```

Treating the edge token `this` as a whole word would look up postings for
`this`, never see that line, and drop a real match with no error. The prefix and
suffix lookups in §5.3 are the sound way to use an edge token: they ask "which
corpus words *end* with `this`?", which is a question the index can answer
correctly.

`tests/test_index_soundness.py` pins this case specifically, plus ~4,000
differential comparisons against brute force on adversarial vocabularies where
every word embeds another.

### 5.5 Persistence

Per `SPEC.md` §7.4, the **default path builds in-process on every run** — the
assignment describes one program in two stages and prints its readiness banner
after the build, so the build is user-visible. `save`/`load` therefore lives
behind a flag, primarily to keep your own dev loop fast.

This is the one decision worth revisiting **with a measurement in hand**: if your
M3 build takes minutes on the full 121 MB corpus, persistence stops being a
convenience and becomes the default. Bring the number to M3 and the team decides
then.

---

## 6. `scripts/build_index.py`

A CLI entry point that builds the index from a corpus root and writes it to disk.
Print build time, sentence count, distinct word count, and peak RSS — those
numbers go straight into the README at M4.

---

## 7. `tests/fixtures/`

A tiny corpus committed to the repo: a handful of small `.txt` files in a nested
tree, deliberately including

- files at two or more different depths,
- blank lines and a punctuation-only line (both must be excluded),
- lines with mixed case and heavy punctuation,
- at least two identical sentences in *different* files,
- lines whose sort order differs from their file order, so the ordering contract
  is actually exercised,
- the assignment's `example.txt` five-line scenario, which Monjed needs for his
  end-to-end test.

Keep it small enough to reason about by hand — a dozen lines total, not a
thousand.

---

## 8. Definition of done

- [ ] Fixture corpus loads; the `(normalized_sentence, source_text,
      offset)` ordering contract is asserted by an explicit test
- [ ] Empty-normalized lines excluded; `original_sentence` preserved byte-for-byte
- [ ] `alphabet` derived from the corpus, not hardcoded
- [ ] `find_lines_containing` matches a brute-force scan on the fixture, for
      patterns with 0, 1 and several interior tokens
- [ ] Laziness proven by test: consuming only the first result does not walk the
      whole posting list
- [ ] Ascending order asserted
- [ ] Full 121 MB corpus builds; build time and peak RSS measured and recorded
- [ ] `save`/`load` round-trips to an index that answers identically
- [ ] No imports from `autocomplete.py` or `cli.py`
