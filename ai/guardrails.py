"""Guardrail: AI text must describe evidence, never judge the candidate.

Any sentence containing a competency verdict or a score prediction is removed and replaced by a
notice. This is applied to every AI-generated interpretive text (LLM descriptions and summaries,
vision tags, mapper rationales and statements) before it is stored.

Verbatim ASR transcripts are a record of what the candidate *said* and are not rewritten (that
would alter evidence); they are scanned with `find_violations` and flagged instead.

The patterns are deliberately conservative: a false positive costs one neutral sentence, a false
negative would put a verdict in front of the assessor.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

NOTICE = "[Removed by guardrail: competency judgements and scores are reserved for the assessor.]"

_DEV = r"ऀ-ॿ"  # Devanagari block


def _hi(word: str) -> str:
    """Devanagari word with script-aware boundaries (\\b is unreliable around matras)."""
    return rf"(?<![{_DEV}]){word}(?![{_DEV}])"


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("competency_verdict", re.compile(r"\b(?:not\s+yet\s+competent|in-?competent|competent(?:ly)?)\b", re.I)),
    # "pass"/"fail" as outcomes; physical "pass through/over/along..." is allowed.
    ("pass_fail", re.compile(
        r"\b(?:pass(?:es|ed)?|fail(?:s|ed)?)\b(?!\s+(?:through|over|under|into|along|across|around|behind|between|the\s+cable|the\s+wire))",
        re.I)),
    ("qualification_verdict", re.compile(r"\b(?:un|dis)?qualif(?:ied|ies|y)\b", re.I)),
    ("certification", re.compile(r"\bcertif(?:y|ied|ies|ying|iable)\b", re.I)),
    ("score_prediction", re.compile(r"\bscor(?:e|es|ed|ing)\s+(?:of\s+|is\s+|=\s*|:\s*)?\d", re.I)),
    ("score_fraction", re.compile(r"\b\d+(?:\.\d+)?\s*/\s*\d+\b|\b\d+\s+out\s+of\s+\d+\b", re.I)),
    ("marks_prediction", re.compile(r"\b\d+(?:\.\d+)?\s+marks?\b", re.I)),
    ("award_recommendation", re.compile(
        r"\bshould\s+(?:be\s+)?(?:awarded|given|granted|receive)\b|\bdeserves?\b|\baward(?:ed)?\s+(?:a\s+|the\s+)?(?:score|marks?|grade|certificate)\b",
        re.I)),
    ("grade_verdict", re.compile(r"\b(?:grade[ds]?\s+(?:as\s+)?[A-F][+-]?)\b")),
    # Hindi equivalents
    ("hi_competent", re.compile(_hi("(?:सक्षम|असक्षम|अक्षम|दक्ष)"))),
    ("hi_pass_fail", re.compile(_hi("(?:पास|फेल|फ़ेल|उत्तीर्ण|अनुत्तीर्ण)"))),
    ("hi_qualified", re.compile(_hi("(?:योग्य|अयोग्य|प्रमाणित)"))),
    ("hi_marks", re.compile(r"\d+\s*(?:अंक|नंबर)")),
]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।])\s+")


@dataclass
class GuardrailResult:
    text: str
    violations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


def find_violations(text: str | None) -> list[str]:
    if not text:
        return []
    return sorted({name for name, pat in _PATTERNS if pat.search(text)})


def is_clean(text: str | None) -> bool:
    return not find_violations(text)


def neutralise(text: str | None) -> GuardrailResult:
    """Drop every sentence that contains a verdict; replace with a single notice if anything was dropped."""
    if not text:
        return GuardrailResult(text=text or "")
    kept: list[str] = []
    violations: set[str] = set()
    for sentence in _SENTENCE_SPLIT.split(text.strip()):
        v = find_violations(sentence)
        if v:
            violations.update(v)
        else:
            kept.append(sentence)
    if not violations:
        return GuardrailResult(text=text)
    out = " ".join(kept + [NOTICE]).strip()
    return GuardrailResult(text=out, violations=sorted(violations))


def filter_tags(tags: list[str] | None) -> tuple[list[str], list[str]]:
    """Drop tags that are verdicts. Returns (clean_tags, violations)."""
    clean: list[str] = []
    violations: set[str] = set()
    for t in tags or []:
        v = find_violations(t)
        if v:
            violations.update(v)
        else:
            clean.append(t)
    return clean, sorted(violations)
