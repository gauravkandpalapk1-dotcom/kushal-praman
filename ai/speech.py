"""Speech-to-text adapters.

FasterWhisperASR runs only when ASR_PROVIDER=faster_whisper AND the package is installed
(imported lazily). Otherwise it reports itself unavailable and the pipeline skips the step.
DemoASR returns the seeded transcript for the demo asset only.
"""
from __future__ import annotations

import importlib.util
import threading
from pathlib import Path

from ai.base import AdapterError, Availability, SpeechAdapter, SpeechResult, TranscriptSegment
from ai.demo_provider import MODEL as DEMO_MODEL
from ai.demo_provider import PROVIDER as DEMO_PROVIDER
from ai.demo_provider import DemoProvider


class FasterWhisperASR(SpeechAdapter):
    provider = "faster-whisper"
    mode = "real"

    def __init__(self, model_size: str = "small", enabled: bool = True):
        self.model = f"whisper-{model_size}"
        self._size = model_size
        self._enabled = enabled
        self._model = None
        self._lock = threading.Lock()

    def availability(self) -> Availability:
        if not self._enabled:
            return Availability(False, "ASR disabled (ASR_PROVIDER=none).")
        if importlib.util.find_spec("faster_whisper") is None:
            return Availability(False, "faster-whisper is not installed (pip install faster-whisper).")
        return Availability(True, f"faster-whisper ({self._size}) on CPU, int8.")

    def _load(self):
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel  # lazy, optional dependency

                self._model = WhisperModel(self._size, device="cpu", compute_type="int8")
            return self._model

    def transcribe(self, path: Path, *, language_hint: str | None = None) -> SpeechResult:
        try:
            model = self._load()
            segments, info = model.transcribe(str(path), language=language_hint or None, vad_filter=True)
            out = [
                TranscriptSegment(round(s.start, 2), round(s.end, 2), s.text.strip(), info.language)
                for s in segments if s.text.strip()
            ]
        except Exception as exc:  # noqa: BLE001 - surface any runtime failure as a step failure
            raise AdapterError(f"faster-whisper failed: {type(exc).__name__}: {str(exc)[:160]}") from exc
        return SpeechResult(self.provider, self.model, "real", info.language, out)


class DemoASR(SpeechAdapter):
    provider = DEMO_PROVIDER
    model = DEMO_MODEL
    mode = "demo"

    def __init__(self, demo: DemoProvider):
        self.demo = demo

    def availability(self) -> Availability:
        ok = self.demo.fixture_path.is_file()
        return Availability(ok, "Seeded transcript for the demo asset only (matched by SHA-256)." if ok else "Fixture missing.")

    def transcribe(self, path: Path, *, language_hint: str | None = None) -> SpeechResult:
        fx = self.demo.fixture
        lang = fx.get("language")
        segs = [
            TranscriptSegment(float(t["start_s"]), float(t["end_s"]), t["text"], lang, t.get("translation_en"))
            for t in fx.get("transcript", [])
        ]
        return SpeechResult(self.provider, self.model, "demo", lang, segs)
