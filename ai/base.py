"""Adapter interfaces and result dataclasses for the evidence-intelligence pipeline.

Every result carries `provider`, `model` and `mode`:
  - "real"         produced by an actually running service (ffmpeg, a local model, an API call)
  - "demo"         deterministic seeded fixture, ONLY for the known demo media (matched by SHA-256)
  - "unavailable"  the service is not installed / not configured; nothing was produced

Adapters never fabricate output. If they cannot run, `availability()` says why and the pipeline
records the step as skipped.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Mode = Literal["real", "demo", "unavailable"]


class AdapterError(RuntimeError):
    """Raised by an adapter when a configured service fails at run time."""


@dataclass
class Availability:
    available: bool
    detail: str


@dataclass
class TimeSpan:
    start_s: float
    end_s: float


@dataclass
class TranscriptSegment:
    start_s: float
    end_s: float
    text: str
    language: str | None = None
    translation_en: str | None = None


@dataclass
class SpeechResult:
    provider: str
    model: str
    mode: Mode
    language: str | None
    segments: list[TranscriptSegment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SegmentTags:
    start_s: float
    end_s: float
    tags: list[str]


@dataclass
class VisionResult:
    provider: str
    model: str
    mode: Mode
    tags: list[SegmentTags] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OCRResult:
    provider: str
    model: str
    mode: Mode
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SegmentDescription:
    start_s: float
    end_s: float
    description: str


@dataclass
class LLMResult:
    provider: str
    model: str
    mode: Mode
    descriptions: list[SegmentDescription] = field(default_factory=list)
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ServiceStatus:
    """What /health reports per AI service."""

    key: str
    name: str
    provider: str
    model: str | None
    available: bool
    mode: Mode
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class _Adapter(ABC):
    provider: str = "none"
    model: str = ""
    mode: Mode = "real"

    @abstractmethod
    def availability(self) -> Availability: ...


class SpeechAdapter(_Adapter):
    @abstractmethod
    def transcribe(self, path: Path, *, language_hint: str | None = None) -> SpeechResult: ...


class VisionAdapter(_Adapter):
    @abstractmethod
    def describe(self, path: Path, *, kind: str, spans: list[TimeSpan]) -> VisionResult: ...


class OCRAdapter(_Adapter):
    @abstractmethod
    def extract(self, path: Path, *, mime_type: str) -> OCRResult: ...


class LLMAdapter(_Adapter):
    @abstractmethod
    def describe_segments(self, segments: list[dict[str, Any]], pcs: list[dict[str, Any]]) -> LLMResult:
        """Neutral, observable descriptions per segment, bound to the PC text. Never a verdict or score."""
