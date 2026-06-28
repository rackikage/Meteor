"""Query expansion: phonetic, fuzzy, semantic, and substring variants."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ExpandedQuery:
    original: str
    phonetic_keys: list[str] = field(default_factory=list)
    substrings: list[str] = field(default_factory=list)
    word_variants: list[list[str]] = field(default_factory=list)
    combinations: list[str] = field(default_factory=list)
    ngrams: list[str] = field(default_factory=list)
    normalized: str = ""


class PhoneticEncoder:

    @staticmethod
    def dmetaphone(word: str) -> tuple[str, str]:
        word = word.upper()
        if not word:
            return ("", "")

        result = []
        for ch in word:
            if ch in "AEIOU":
                if not result or result[-1] != "A":
                    result.append("A")
            elif ch in "BCKQ":
                result.append("K")
            elif ch in "DT":
                result.append("T")
            elif ch == "F":
                result.append("F")
            elif ch in "GJ":
                result.append("J")
            elif ch == "H":
                result.append("H")
            elif ch == "L":
                result.append("L")
            elif ch in "MN":
                result.append("N")
            elif ch == "P":
                result.append("P")
            elif ch == "R":
                result.append("R")
            elif ch in "SX":
                result.append("S")
            elif ch in "V":
                result.append("F")
            elif ch in "W":
                result.append("W")
            elif ch == "Z":
                result.append("S")

        primary = "".join(result)[:8]
        primary = re.sub(r"(.)\1+", r"\1", primary)
        return (primary, primary)

    @staticmethod
    def soundex(word: str) -> str:
        word = word.upper()
        if not word:
            return ""

        mapping = {
            "B": "1", "F": "1", "P": "1", "V": "1",
            "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
            "D": "3", "T": "3",
            "L": "4",
            "M": "5", "N": "5",
            "R": "6",
        }

        result = word[0]
        prev = mapping.get(word[0], "0")

        for ch in word[1:]:
            code = mapping.get(ch, "")
            if code and code != prev:
                result += code
                prev = code
            if len(result) == 4:
                break

        return result.ljust(4, "0")[:4]


class QueryExpander:

    def __init__(self) -> None:
        self._phonetic = PhoneticEncoder()

    def expand(self, raw: str) -> ExpandedQuery:
        normal = self._normalize(raw)
        words = normal.split()

        phonetic_keys = []
        for w in words:
            pri, _ = self._phonetic.dmetaphone(w)
            if pri:
                phonetic_keys.append(pri)
            sx = self._phonetic.soundex(w)
            if sx:
                phonetic_keys.append(f"sx:{sx}")

        degarbled = re.sub(r"(.)\1{2,}", r"\1", normal)

        substrings = []
        for min_len in [2, 3, 4]:
            for i in range(len(normal) - min_len + 1):
                substrings.append(normal[i:i + min_len])
        substrings = list(set(substrings))

        ngrams = []
        for n in [1, 2, 3]:
            for i in range(len(words) - n + 1):
                ngrams.append(" ".join(words[i:i + n]))

        combinations = list(set([
            normal,
            degarbled,
            " ".join(words),
            " ".join(reversed(words)),
            re.sub(r"[aeiou]+", "", normal),
            re.sub(r"[^aeiou]+", "", normal),
        ]))

        return ExpandedQuery(
            original=raw,
            phonetic_keys=list(set(phonetic_keys)),
            substrings=substrings,
            ngrams=list(set(ngrams)),
            combinations=[c for c in combinations if len(c) > 1],
            normalized=normal,
        )

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def fuzzy_match(self, candidate: str, target: str, threshold: float = 70.0) -> bool:
        try:
            from rapidfuzz import fuzz
            scores = [
                fuzz.ratio(candidate, target),
                fuzz.partial_ratio(candidate, target),
                fuzz.token_sort_ratio(candidate, target),
                fuzz.token_set_ratio(candidate, target),
            ]
            return max(scores) >= threshold
        except ImportError:
            return self._simple_fuzzy(candidate, target, threshold)

    @staticmethod
    def _simple_fuzzy(candidate: str, target: str, threshold: float = 70.0) -> bool:
        candidate = candidate.lower().strip()
        target = target.lower().strip()
        if not candidate or not target:
            return False
        if candidate == target:
            return True
        if candidate in target or target in candidate:
            return True

        shorter = candidate if len(candidate) < len(target) else target
        longer = target if len(candidate) < len(target) else candidate
        ratio = len(shorter) / len(longer) * 100
        return ratio >= threshold
