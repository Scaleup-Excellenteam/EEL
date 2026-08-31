# EEL Autocomplete Project - Specification

## 1. Project Goal

Build an autocomplete system that searches a collection of text files and returns
the 5 best matching sentences for text entered by the user.

The system must support:

- Exact substring matching
- Maximum one character error:
  - substitution
  - insertion
  - deletion
- Case-insensitive matching
- Ignoring punctuation during matching
- Collapsing repeated spaces
- Scoring according to the assignment rules
- Returning the best 5 matches
- Alphabetical ordering when scores are equal

The project will be implemented in Python.

---

## 2. Architecture

The project contains two main parts.

### Offline

Responsible for preparing the data.

Flow:

Text files
→ Load sentences
→ Normalize sentences
→ Build search index
→ Ready for searching

### Online

Responsible for handling user queries.

Flow:

User query
→ Normalize query
→ Find candidates
→ Check exact / one-error match
→ Calculate score
→ Sort
→ Return best 5

---

## 3. Shared Models

Both developers must use the same models.

### SentenceData

Represents one sentence from the corpus.

Fields:

- original_sentence
- normalized_sentence
- source_text
- offset

### AutoCompleteData

Represents one autocomplete result.

Fields:

- completed_sentence
- source_text
- offset
- score

Required public function:

get_best_k_completions(prefix: str) -> List[AutoCompleteData]

---

## 4. Developer 1 - Offline / Data

Branch:

feature/offline-index

Responsible for:

- src/normalizer.py
- src/loader.py
- src/index.py
- offline tests

Tasks:

1. Find all text files recursively.
2. Read every line as a sentence.
3. Store the original sentence.
4. Store the source file and offset.
5. Normalize sentences.
6. Build the search index.
7. Provide candidates to the online part.

Developer 1 does not implement scoring or final ranking.

---

## 5. Developer 2 - Online / Search

Branch:

feature/online-search

Responsible for:

- src/matcher.py
- src/scorer.py
- src/autocomplete.py
- src/cli.py
- online tests

Tasks:

1. Receive the user query.
2. Normalize the query using the shared normalizer.
3. Check exact substring matches.
4. Support one substitution.
5. Support one insertion.
6. Support one deletion.
7. Calculate the score.
8. Rank matching sentences.
9. Return the best 5.
10. Sort equal-score results alphabetically.
11. Handle interactive input.

Developer 2 does not implement file loading or indexing.

---

## 6. Integration Contract

Developer 1 provides SentenceData objects to the search system.

Developer 2 consumes those SentenceData objects and returns AutoCompleteData objects.

Do not create duplicate implementations of:

- SentenceData
- AutoCompleteData
- normalization

Shared interfaces must not be changed without agreement between both developers.

---

## 7. Git Rules

Both developers start from the same main branch.

Do not work directly on main after branches are created.

Developer 1 works only on:

feature/offline-index

Developer 2 works only on:

feature/online-search

Avoid editing files owned by the other developer unless both developers agree.

Before merging:

1. Commit all work.
2. Pull latest main.
3. Merge main into the feature branch if necessary.
4. Run tests.
5. Create the merge / pull request.

---

## 8. Definition of Done

The project is finished when:

- All corpus files are loaded correctly.
- Exact substring matching works.
- Case-insensitive matching works.
- Punctuation is ignored during matching.
- Repeated spaces are handled.
- One substitution works.
- One insertion works.
- One deletion works.
- More than one edit is rejected.
- Scores follow the assignment rules.
- The best 5 results are returned.
- Equal scores are sorted alphabetically.
- Original sentence information is returned.
- Source file and offset are returned.
- The interactive program works.
- Both developers understand the complete solution.