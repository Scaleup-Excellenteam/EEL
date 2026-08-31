# Developer 1 — Elav · Scoring Core

**Branch:** `feature/scoring-core`
**Files you own:** `src/normalizer.py`, `src/scorer.py`, `tests/test_normalizer.py`, `tests/test_scorer.py`, `tests/reference.py`
**Files you must not touch:** `src/loader.py`, `src/index.py` (Qusai) · `src/autocomplete.py`, `src/cli.py`, `main.py` (Monjed)
**Depends on:** nothing. You can start immediately.
**Shared spec:** [`../SPEC.md`](../SPEC.md)

---

## 1. Your mission

You own the correctness heart of the system: the normalization rules, the four
score formulas, and the **score ladder** — the generator that turns fuzzy
matching into a sequence of exact substring searches in descending score order.

Everything the other two build is verified against your code, so it must land
first. Your entire track is **pure functions with zero dependencies**: you can
test exhaustively without a corpus, without an index, and without the CLI.

> Note: `src/normalizer.py` was the offline developer's file in the old
> two-developer spec. It moved to you because normalization is what *defines*
> "matching characters", so it belongs beside the score formulas that depend on
> it. Qusai imports it; he does not own it.

You do not implement file loading, indexing, or the CLI.

---

## 2. Why the ladder exists — read before writing code

The score depends **only** on the query length and the edit's type and position.
It does *not* depend on which sentence matched.

So the achievable scores form a fixed ladder known before touching the corpus.
Walk it top-down, and at each tier search for the already-corrected query
variants as **exact substrings**. The first 5 distinct lines found are provably
the answer.

This is why nobody in this project ever runs an edit-distance computation against
3.45 M lines. Your `score_ladder` is what makes that true, and it is why
`src/matcher.py` from the old spec no longer exists.

---

## 3. `src/normalizer.py`

```python
def normalize(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace runs to a single space,
    strip leading/trailing whitespace."""
```

Rules:

- Lowercase everything.
- **Remove** punctuation entirely — do not replace it with a space. `be, that`
  normalizes to `be that`, which is 7 characters, and 7 is what the assignment's
  own example needs to score 14. Replacing with a space would give 8 and score 16.
- Collapse any run of whitespace to one space. Spaces **count as characters** for
  scoring.
- **Preserve digits.** They are not punctuation. The assignment's `2o be` example
  substitutes a digit, so digits must survive normalization.
- Strip leading and trailing whitespace.

The corpus is English technical documentation containing `@!.,$` and much more.
Keeping only `[a-z0-9 ]` after lowercasing is the simple, defensible rule — write
it that way and say so in a comment.

### Tests

- Each assignment example's normalization, asserted directly.
- `"To be or not to be, that is the question."` →
  `"to be or not to be that is the question"`
- Idempotence: `normalize(normalize(x)) == normalize(x)` across a spread of inputs.
- A run of many spaces collapses to exactly one.
- Digits survive; punctuation does not.

---

## 4. `src/scorer.py` — the four formulas

```python
SUBSTITUTION_PENALTIES = (5, 4, 3, 2, 1)   # last value repeats for positions 5+
INDEL_PENALTIES        = (10, 8, 6, 4, 2)  # last value repeats for positions 5+

def substitution_penalty(position: int) -> int   # 1-based
def indel_penalty(position: int) -> int          # 1-based

def score_exact(length: int) -> int
def score_substitution(length: int, position: int) -> int
def score_extra_char(length: int, position: int) -> int
def score_missing_char(length: int, position: int) -> int
```

With `L` = normalized query length:

| Case | Matching chars | Score |
|---|---|---|
| Exact substring | L | `2L` |
| Substitution at position *i* | L − 1 | `2(L−1) − sub(i)` |
| Query has an **extra** char at *i* | L − 1 | `2(L−1) − indel(i)` |
| Query is **missing** a char at *i* | L | `2L − indel(i)` |

**Get the asymmetry right — it is the easiest thing in the project to get
wrong.** A *missing* character still earns full matching points for every
character the user actually typed; only the inserted character earns nothing. An
*extra* character costs one matching point **and** the penalty.

### Position semantics — verified, do not re-derive

| Edit | Position means |
|---|---|
| Substitution at *i* | 1-based index in the query (same in the result) |
| **Extra** char at *i* (delete it) | 1-based index in the **original query** |
| **Missing** char at *i* (insert it) | 1-based index the inserted char **occupies in the result** |

For insertion the assignment says: *"for a missing character, use the position
where it is inserted."* The index the new character occupies in the result and the
1-based insertion index in the query are the same number, so there is no
query-vs-result ambiguity.

The trap is an **off-by-one**: using the index of the character you insert
*after*, instead of the index the new character *lands on*. Worked check — query
`or nt` (L=5), insert `o` to reach `or not`. In the result `o,r,_,n,o,t` the new
`o` occupies index 5, so penalty 2 and `2×5 − 2 = 8`, matching the assignment.
Had you taken the preceding `n` at index 4 you would have applied penalty 4 and
scored 6. Wrong.

### Tests — the assignment hands you your test suite

Sentence: *"To be or not to be, that is the question."*

| Query | Expected | Why |
|---|---|---|
| `To be` | 10 | 5 matching chars including the space |
| `or Not` | 12 | 6 matching chars, case ignored |
| `be, that` | 14 | 7 matching chars after the comma is removed |
| `2o be` | 3 | substitute `2`→`t` at position 1: `2×4 − 5` |
| `to pe` | 6 | substitute `p`→`b` at position 4: `2×4 − 2` |
| `or knot` | 8 | extra `k` at position 4: `2×6 − 4` |
| `or nt` | 8 | missing `o` at position 5: `2×5 − 2` |
| `not be` | no match | needs more than one edit |

Also port the Hebrew body's examples — same four formulas, independent
cross-check:

| Query (sentence: *"להיות או לא להיות, זאת השאלה"*) | Expected | Case | L | Position |
|---|---|---|---|---|
| `להיות או לא` | 22 | exact | 11 | — |
| `להיות או לו` | 19 | substitution | 11 | 11 |
| `להיןת או לא` | 18 | substitution | 11 | 4 |
| `להייות או לא` | 18 | extra char | 12 | 4 |
| `להות או לא` | 14 | missing char | 10 | 3 |

> ⚠️ **Call the Hebrew examples through the scoring functions directly — never
> through `normalize()`.** The corpus is English-only, so §3 defines
> normalization as "keep only `[a-z0-9 ]`", which strips every Hebrew character
> and reduces these queries to spaces. The Hebrew examples verify the four
> **formulas** — hence the explicit L and position columns. The English examples
> are what exercise the normalization path. Mixing the two produces a failing
> test that looks like a scoring bug and is not one.

---

## 5. `src/scorer.py` — `score_ladder`, your main deliverable

```python
@dataclass(frozen=True)
class Variant:
    text: str    # the corrected query, to be searched as an exact substring
    score: int

def score_ladder(query: str, alphabet: str) -> Iterator[list[Variant]]:
    """Yield groups of variants in STRICTLY DESCENDING score order.
    All variants in a yielded group share one score.
    `query` must already be normalized. `alphabet` comes from the loader — do
    not hardcode a-z."""
```

### The tiers, in order

```
2L      exact — the query itself
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

### Variant construction

For a normalized query `q` of length `L`, with 1-based `i`:

| Edit | Variants |
|---|---|
| exact | `q` |
| substitution at *i* | `q[:i-1] + c + q[i:]` for every `c in alphabet`, `c != q[i-1]` |
| extra char at *i* | `q[:i-1] + q[i:]` |
| missing char at *i* | `q[:i-1] + c + q[i-1:]` for every `c in alphabet`, `i` in `1..L+1` |

### Four filters you must apply

Not polish — skipping these produces wrong answers or wasted searches.

1. **Global dedup, keeping the first (highest-scoring) occurrence.** Distinct
   (edit, position) pairs can produce identical strings. For `q = "aa"`, inserting
   `a` at positions 1, 2 and 3 all yield `"aaa"`; deleting index *i* when
   `q[i] == q[i+1]` yields the same string twice. Because you walk tiers in
   descending order, keeping the *first* occurrence automatically gives each
   variant its best possible score.
2. **Drop variants containing a double space.** Normalized corpus lines never
   contain `"  "`, so such a variant can never match. Inserting a space beside an
   existing one is the usual source.
3. **Drop empty variants.** Deleting the only character of a 1-character query
   yields `""`, which would match every line in the corpus.
4. **Drop non-positive scores** (`SPEC.md` §7.5). `L=1` with a substitution at
   position 1 scores `2×0 − 5 = −5`. Score ≤ 0 means zero matching characters —
   nothing the user typed actually matched. Almost unobservable in practice, since
   for a 1-character query the exact tier fills all five slots long before any
   penalized tier is reached, but without it a pathological query returns
   negative-scored garbage.

### Tests

- Scores across consecutive yielded groups are strictly descending.
- No variant string is ever yielded twice across the whole ladder.
- No yielded variant is empty, contains `"  "`, or has a non-positive score.
- For each assignment example, the expected variant appears in the group whose
  score matches the expected score.
- `L=1` and `L=2` do not crash and yield sane ladders.

---

## 6. `tests/reference.py` — the correctness oracle

A deliberately slow, obviously-correct implementation: for one query, scan every
sentence and compute the best achievable score by brute force over all four edit
kinds at all positions.

This is **test-only code**, never imported by the running system. Its purpose is
to let Monjed's fast ladder-based path be validated by exhaustive comparison on
the fixture corpus. Write it for obviousness, not speed — if you find yourself
optimizing it, you are defeating its purpose.

Done when: for a generated query set (short, long, with and without each edit
kind) the reference and the fast path return identical result lists on the
fixture corpus.

---

## 7. Definition of done

- [ ] All twelve assignment examples pass as tests, English and Hebrew
- [ ] Hebrew examples bypass `normalize()`, per the warning in §4
- [ ] Insertion position semantics verified by test
- [ ] `score_ladder` proven strictly descending, no duplicate variants
- [ ] All four filters of §5 implemented and tested
- [ ] `reference.py` agrees with the fast path on the fixture corpus
- [ ] No imports from `loader.py`, `index.py`, `autocomplete.py` or `cli.py`

---

## 8. Your integration-owner duties

- **M0** — chair the interface freeze on `src/models.py`. Nothing else starts
  until it is done.
- **M2** — first end-to-end wiring on the fixture corpus.
- **M4** — full-corpus verification, latency measurements, README.
