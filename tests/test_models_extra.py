"""Additional tests for src/models.py: value equality and hashing, which the
existing model tests (sort_key, __str__, frozen-ness) never check directly."""

import dataclasses

import pytest

from src.models import AutoCompleteData, SentenceData


def test_autocompletedata_equality_and_hash_by_value():
    a = AutoCompleteData("Alpha: this is a demo.", "example.txt", 1, 14)
    b = AutoCompleteData("Alpha: this is a demo.", "example.txt", 1, 14)
    different_score = AutoCompleteData("Alpha: this is a demo.", "example.txt", 1, 10)

    assert a == b
    assert hash(a) == hash(b)
    assert a != different_score
    # Being hashable and equal-by-value means it can dedupe correctly in a set.
    assert len({a, b, different_score}) == 2


def test_sentencedata_is_frozen_and_equal_by_value():
    first = SentenceData("Hi there.", "hi there", "a.txt", 1)
    same = SentenceData("Hi there.", "hi there", "a.txt", 1)
    different_offset = SentenceData("Hi there.", "hi there", "a.txt", 2)

    assert first == same
    assert hash(first) == hash(same)
    assert first != different_offset
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.offset = 99  # type: ignore[misc]
