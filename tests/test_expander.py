"""Tests for query expansion engine."""

from __future__ import annotations

import pytest

from app.search.expander import PhoneticEncoder, QueryExpander


class TestPhoneticEncoder:

    def test_dmetaphone_basic_word(self):
        pri, sec = PhoneticEncoder.dmetaphone("hello")
        assert pri
        assert isinstance(pri, str)
        assert len(pri) > 0

    def test_dmetaphone_empty(self):
        pri, sec = PhoneticEncoder.dmetaphone("")
        assert pri == ""
        assert sec == ""

    def test_dmetaphone_deduplicates_consecutive(self):
        pri, _ = PhoneticEncoder.dmetaphone("llama")
        assert "LL" not in pri

    def test_soundex_basic(self):
        result = PhoneticEncoder.soundex("Robert")
        assert result
        assert len(result) == 4
        assert result[0] == "R"

    def test_soundex_empty(self):
        assert PhoneticEncoder.soundex("") == ""

    def test_soundex_padding(self):
        result = PhoneticEncoder.soundex("Ash")
        assert len(result) == 4

    def test_soundex_similar_names(self):
        r1 = PhoneticEncoder.soundex("Smith")
        r2 = PhoneticEncoder.soundex("Smyth")
        assert r1 == r2


class TestQueryExpander:

    def test_expand_basic(self):
        expander = QueryExpander()
        result = expander.expand("hello world")
        assert result.original == "hello world"
        assert result.normalized == "hello world"
        assert len(result.phonetic_keys) > 0
        assert len(result.combinations) > 0

    def test_expand_garbled_query(self):
        expander = QueryExpander()
        result = expander.expand("he ha ha loooo")
        assert result.normalized == "he ha ha loooo"
        assert len(result.phonetic_keys) > 0
        assert len(result.substrings) > 0
        assert len(result.ngrams) > 0

    def test_expand_normalizes_whitespace(self):
        expander = QueryExpander()
        result = expander.expand("  hello   world  ")
        assert result.normalized == "hello world"

    def test_expand_normalizes_case(self):
        expander = QueryExpander()
        result = expander.expand("HELLO World")
        assert result.normalized == "hello world"

    def test_expand_removes_punctuation(self):
        expander = QueryExpander()
        result = expander.expand("hello, world!")
        assert "," not in result.normalized
        assert "!" not in result.normalized

    def test_expand_generates_ngrams(self):
        expander = QueryExpander()
        result = expander.expand("one two three four")
        assert "one" in result.ngrams
        assert "one two" in result.ngrams
        assert "one two three" in result.ngrams

    def test_expand_generates_substrings(self):
        expander = QueryExpander()
        result = expander.expand("hello")
        assert "he" in result.substrings
        assert "hel" in result.substrings
        assert "hell" in result.substrings

    def test_expand_degarbles_repeated_chars(self):
        expander = QueryExpander()
        result = expander.expand("loooo")
        assert "lo" in result.combinations

    def test_expand_consonants_only(self):
        expander = QueryExpander()
        result = expander.expand("hello")
        assert "hll" in result.combinations

    def test_expand_vowels_only(self):
        expander = QueryExpander()
        result = expander.expand("hello")
        assert "eo" in result.combinations

    def test_expand_reversed(self):
        expander = QueryExpander()
        result = expander.expand("hello world")
        assert "world hello" in result.combinations

    def test_fuzzy_match_exact(self):
        expander = QueryExpander()
        assert expander.fuzzy_match("hello", "hello") is True

    def test_fuzzy_match_similar(self):
        expander = QueryExpander()
        assert expander.fuzzy_match("hello", "helo", threshold=70.0) is True

    def test_fuzzy_match_different(self):
        expander = QueryExpander()
        assert expander.fuzzy_match("hello", "xyz", threshold=90.0) is False

    def test_fuzzy_match_empty(self):
        expander = QueryExpander()
        assert expander.fuzzy_match("", "hello") is False

    def test_expand_single_word(self):
        expander = QueryExpander()
        result = expander.expand("test")
        assert result.normalized == "test"
        assert len(result.phonetic_keys) > 0

    def test_expand_preserves_original(self):
        expander = QueryExpander()
        result = expander.expand("He Ha Ha Loooo")
        assert result.original == "He Ha Ha Loooo"
