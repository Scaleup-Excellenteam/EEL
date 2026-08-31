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
> `(original_sentence.casefold(), source_text, offset)`.**

This is **the same key** as `AutoCompleteData.sort_key`. Note it is the
**original** sentence case-folded, *not* the normalized form. If your key and
`sort_key` disagree, your ordering and Monjed's ordering disagree and the output
comes back mis-ordered.

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

### 5.2 Query strategy: rarest interior word

1. Split `pattern` on spaces.
2. Keep only **strictly interior** tokens (§5.3).
3. Of those, pick the one with the **smallest posting list**.
4. Walk that posting list in ascending order, lazily.
5. Verify each candidate with `pattern in corpus.normalized(line_id)`.
6. Yield the line ID if it verifies.

Instead of scanning 3.45 M lines you scan a few hundred. Verification is what
makes this exact rather than approximate — the index narrows candidates, it does
not decide matches.

### 5.3 Only strictly interior tokens are safe

In the pattern `or no`, the trailing `no` may be part of `not` in the sentence,
and the leading `or` may be part of `for`. Edge tokens are **fragments**, not
words, so looking them up in a word index would miss real matches.

A token is strictly interior when it has a space on both sides *within the
pattern*:

- the first token is interior only if `pattern` starts with a space
- the last token is interior only if `pattern` ends with a space
- every other token is interior

So `or no` has **no** interior token and needs the fallback. `or not the` has
one: `not`.

### 5.4 Short-query fallback

For patterns with no strictly interior token, in order of preference:

1. If an edge token happens to be a complete corpus word, use it anyway as a
   candidate source, then verify. It may over-generate candidates but never
   under-generates — verification catches the rest.
2. Otherwise brute-scan in ascending line-ID order with early termination. This
   is legal precisely because of the ordering contract, and short patterns match
   enormous numbers of lines, so it terminates almost immediately.

**Do not build a trigram index speculatively.** Measure the fallback first. If
measurement shows it is the bottleneck, that is the moment to reach for it.

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

- [ ] Fixture corpus loads; the `(original_sentence.casefold(), source_text,
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
