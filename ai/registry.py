"""Adapter registry: picks real adapters from settings, pairs them with the demo adapters, and
reports availability for /health.

Selection rule used by the pipeline:
  * KP_MODE=demo and the evidence IS the known demo asset  -> demo adapters (mode "demo")
  * otherwise                                               -> real adapters; unavailable => skipped
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai.base import LLMAdapter, OCRAdapter, ServiceStatus, SpeechAdapter, VisionAdapter
from ai.demo_provider import DemoProvider
from ai.llm import DemoLLM, LLMClient, ProviderLLM, UnavailableLLM
from ai.ocr import DemoOCR, TesseractOCR
from ai.segmentation import ffmpeg_info
from ai.speech import DemoASR, FasterWhisperASR
from ai.vision import DemoVision, LLMVision, UnavailableVision


@dataclass
class AdapterSet:
    speech: SpeechAdapter
    vision: VisionAdapter
    ocr: OCRAdapter
    llm: LLMAdapter
    demo: bool


def _llm_client(settings: Any) -> LLMClient | None:
    choice = settings.LLM_PROVIDER
    if choice == "none":
        return None
    if choice in ("auto", "claude") and settings.ANTHROPIC_API_KEY:
        return LLMClient("claude", settings.ANTHROPIC_API_KEY, settings.CLAUDE_MODEL)
    if choice in ("auto", "gemini") and settings.GEMINI_API_KEY:
        return LLMClient("gemini", settings.GEMINI_API_KEY, settings.GEMINI_MODEL)
    return None


class Registry:
    def __init__(self, settings: Any, demo: DemoProvider):
        self.settings = settings
        self.demo_provider = demo
        client = _llm_client(settings)
        no_llm = ("LLM disabled (LLM_PROVIDER=none)." if settings.LLM_PROVIDER == "none"
                  else "No LLM API key configured (ANTHROPIC_API_KEY / GEMINI_API_KEY).")
        self.real = AdapterSet(
            speech=FasterWhisperASR(settings.ASR_MODEL, enabled=settings.ASR_PROVIDER == "faster_whisper"),
            vision=LLMVision(client) if client else UnavailableVision(no_llm),
            ocr=TesseractOCR(enabled=settings.OCR_PROVIDER != "none"),
            llm=ProviderLLM(client) if client else UnavailableLLM(no_llm),
            demo=False,
        )
        self.demo = AdapterSet(DemoASR(demo), DemoVision(demo), DemoOCR(demo), DemoLLM(demo), demo=True)

    def use_demo_for(self, is_demo_asset: bool) -> bool:
        return self.settings.KP_MODE == "demo" and is_demo_asset

    def adapters_for(self, is_demo_asset: bool) -> AdapterSet:
        return self.demo if self.use_demo_for(is_demo_asset) else self.real

    def services_status(self) -> list[ServiceStatus]:
        demo_mode = self.settings.KP_MODE == "demo"
        ff = ffmpeg_info()
        out = [ServiceStatus(
            "segmentation", "Segmentation (scene detection)", "ffmpeg", ff.get("version"), ff["available"],
            "real" if ff["available"] else "unavailable",
            f"ffmpeg scene detection, threshold {self.settings.SCENE_THRESHOLD}; fixed {int(self.settings.FALLBACK_WINDOW_S)} s window fallback."
            if ff["available"] else "ffmpeg not found on PATH.",
        )]
        names = {"speech": "Speech-to-text", "vision": "Visual tags", "ocr": "OCR", "llm": "LLM descriptions"}
        for key, name in names.items():
            real = getattr(self.real, key)
            demo = getattr(self.demo, key)
            ra = real.availability()
            real_mode = "real" if ra.available else "unavailable"
            if demo_mode and key != "ocr":
                detail = f"DEMO ANALYSIS for the demo asset (seeded fixture). Other media: {ra.detail}"
                out.append(ServiceStatus(key, name, "demo", demo.model, True, "demo", detail))
            else:
                out.append(ServiceStatus(key, name, real.provider, real.model or None, ra.available, real_mode, ra.detail))
        out.append(ServiceStatus(
            "mapper", "Evidence Mapper", "lexical-baseline", "keyword+PC-text overlap v1", True,
            "demo" if demo_mode else "real",
            ("Real lexical baseline runs on all evidence; the demo asset's mapping comes from the seeded fixture "
             "(baseline ranking recorded alongside). Scores are uncalibrated relevance, not probabilities.")
            if demo_mode else "Real lexical baseline. Scores are uncalibrated relevance, not probabilities.",
        ))
        out.append(ServiceStatus(
            "guardrail", "Guardrail (no competency verdicts)", "rules", "regex v1 (en+hi)", True, "real",
            "Removes competency verdicts and score predictions from AI text before storage.",
        ))
        return out
