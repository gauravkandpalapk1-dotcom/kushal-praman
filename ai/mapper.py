"""Evidence Mapper: REAL, dependency-free lexical baseline (evidence segment -> Performance Criterion).

For each (segment, PC) pair the mapper compares the segment's text (transcript incl. English
translation, vision tags, LLM description, OCR text) with the PC's verbatim text and its curated
keywords (from the seed JSON):

    raw   = sum(1.5 per matched multi-word keyword, 1.0 per matched single keyword,
                0.5 per matched PC-text content word not already covered by a keyword)
    score = raw / (raw + K)            K = 4.0, so score is in [0, 1)

The score is an UNCALIBRATED RELEVANCE SCORE used for ranking. It is NOT a probability that the
evidence supports the PC, and NOT a judgement of the candidate. Calibration (reliability diagram
against assessor confirmations) is pilot work. The planned upgrade is embedding retrieval
(pgvector) with an LLM re-rank; this baseline stays as the transparent fallback.

Output wording is evidential only, e.g.:
    "Potential evidence supporting PC10 found at 00:42–01:08."
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

K = 4.0
DEFAULT_MIN_SCORE = 0.30
SUPPORTS_THRESHOLD = 0.60

_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "i", "in", "into", "is", "it",
    "its", "now", "of", "on", "onto", "or", "other", "the", "then", "this", "to", "with", "am", "making", "make",
    "use", "using", "used", "about", "first", "not", "are", "was", "were", "will", "my", "me",
}
_SUFFIXES = ("ations", "ation", "ated", "ates", "ing", "ers", "er", "ed", "es", "s")
_WORD = re.compile(r"[a-z0-9]+|[ऀ-ॿ]+")


def stem(token: str) -> str:
    for suf in _SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 3:
            token = token[: -len(suf)]
            break
    if len(token) > 3 and token[-1] == token[-2] and token[-1] not in "aeiou":
        token = token[:-1]  # stripp -> strip
    return token


def tokens(text: str) -> list[str]:
    return [stem(t) for t in _WORD.findall((text or "").lower())]


def format_ts(seconds: float) -> str:
    """mm:ss (minutes are not wrapped at 60)."""
    total = int(round(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def statement(pc_code: str, start_s: float, end_s: float) -> str:
    return f"Potential evidence supporting {pc_code} found at {format_ts(start_s)}–{format_ts(end_s)}."


@dataclass
class PCSpec:
    id: int | None
    code: str
    text: str
    keywords: list[str] = field(default_factory=list)
    nos_code: str | None = None


@dataclass
class SegmentText:
    start_s: float
    end_s: float
    transcript: str = ""
    tags: list[str] = field(default_factory=list)
    description: str = ""
    ocr: str = ""
    segment_id: int | None = None

    def full_text(self) -> str:
        return " ".join([self.transcript, " ; ".join(self.tags), self.description, self.ocr])


@dataclass
class Match:
    pc_code: str
    pc_id: int | None
    start_s: float
    end_s: float
    segment_id: int | None
    score: float
    raw: float
    matched_keywords: list[str]
    matched_terms: list[str]

    @property
    def statement(self) -> str:
        return statement(self.pc_code, self.start_s, self.end_s)

    @property
    def signal(self) -> str:
        return "supports" if self.score >= SUPPORTS_THRESHOLD else "partial"

    def rationale(self) -> str:
        found = ", ".join(self.matched_keywords + self.matched_terms) or "none"
        return (
            f"Lexical baseline: the segment's transcript/tags/description share these terms with {self.pc_code}: "
            f"{found}. Uncalibrated relevance {self.score:.2f} (ranking aid, not a probability). "
            "Whether the work meets the standard is for the assessor to judge against the rubric."
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["statement"] = self.statement
        return d


def _contains(seq: list[str], sub: list[str]) -> bool:
    n = len(sub)
    return n > 0 and any(seq[i:i + n] == sub for i in range(len(seq) - n + 1))


def score_segment(seg: SegmentText, pc: PCSpec) -> Match:
    seg_tokens = tokens(seg.full_text())
    seg_set = set(seg_tokens)
    raw = 0.0
    matched_kw: list[str] = []
    covered: set[str] = set()
    for kw in pc.keywords:
        kw_tokens = tokens(kw)
        if kw_tokens and _contains(seg_tokens, kw_tokens):
            raw += 1.5 if len(kw_tokens) > 1 else 1.0
            matched_kw.append(kw)
            covered.update(kw_tokens)
    matched_terms: list[str] = []
    for t in dict.fromkeys(tokens(pc.text)):
        if t in _STOP or len(t) < 3 or t in covered:
            continue
        if t in seg_set:
            raw += 0.5
            matched_terms.append(t)
    score = round(raw / (raw + K), 4) if raw > 0 else 0.0
    return Match(pc.code, pc.id, seg.start_s, seg.end_s, seg.segment_id, score, raw, matched_kw, matched_terms)


def rank(segments: list[SegmentText], pcs: list[PCSpec]) -> dict[str, list[Match]]:
    """Per PC: all segments ranked by relevance (desc, ties -> earlier segment first)."""
    return {
        pc.code: sorted((score_segment(s, pc) for s in segments), key=lambda m: (-m.score, m.start_s))
        for pc in pcs
    }


def rank_per_segment(segments: list[SegmentText], pcs: list[PCSpec]) -> list[dict[str, Any]]:
    """Per segment: PCs ranked by relevance."""
    out = []
    for s in segments:
        ms = sorted((score_segment(s, pc) for pc in pcs), key=lambda m: -m.score)
        out.append({"start_s": s.start_s, "end_s": s.end_s, "segment_id": s.segment_id,
                    "pcs": [{"pc_code": m.pc_code, "score": m.score} for m in ms]})
    return out


def propose(segments: list[SegmentText], pcs: list[PCSpec], *, min_score: float = DEFAULT_MIN_SCORE,
            top_k: int = 1) -> list[Match]:
    """Top-k segments per PC whose relevance is at least `min_score`."""
    out: list[Match] = []
    for matches in rank(segments, pcs).values():
        out.extend([m for m in matches if m.score >= min_score][:top_k])
    return out
