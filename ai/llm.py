"""LLM adapters: neutral, observable segment descriptions bound to the PC text.

Claude (anthropic SDK) and Gemini (google-genai) are optional and imported lazily; each is
available only when its API key is set and its package is installed. Prompts restrict the model
to describing what is observable; output is JSON-only and is passed through ai.guardrails by the
pipeline before storage. DemoLLM returns the seeded descriptions for the demo asset only.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import re
from typing import Any

from ai.base import AdapterError, Availability, LLMAdapter, LLMResult, SegmentDescription
from ai.demo_provider import MODEL as DEMO_MODEL
from ai.demo_provider import PROVIDER as DEMO_PROVIDER
from ai.demo_provider import DemoProvider

SYSTEM_PROMPT = (
    "You assist vocational Recognition of Prior Learning (RPL) assessors by DESCRIBING evidence. "
    "Describe only what is observable or said: tools, materials, actions, sequence, safety equipment. "
    "Relate descriptions to the wording of the Performance Criterion (PC) text you are given. "
    "Never judge the candidate. Never say competent / not yet competent / pass / fail / qualified / "
    "certified, never predict or suggest a score, mark, grade or award, in any language. "
    "The human assessor makes every judgement. Respond with JSON only, no prose outside JSON."
)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise AdapterError("Model did not return JSON.")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise AdapterError(f"Model returned invalid JSON: {exc}") from exc


class LLMClient:
    """Thin JSON-only client over Claude or Gemini (shared by the LLM and vision adapters)."""

    def __init__(self, provider: str, api_key: str, model: str):
        self.provider = provider  # "claude" | "gemini"
        self.api_key = api_key
        self.model = model

    def availability(self) -> Availability:
        module, dist = ("anthropic", "anthropic") if self.provider == "claude" else ("google.genai", "google-genai")
        label = "Claude (anthropic SDK)" if self.provider == "claude" else "Gemini (google-genai)"
        if not self.api_key:
            return Availability(False, f"{label}: no API key configured.")
        try:
            found = importlib.util.find_spec(module) is not None
        except ModuleNotFoundError:
            found = False
        if not found:
            return Availability(False, f"{label}: package '{dist}' not installed.")
        return Availability(True, f"{label}, model {self.model}.")

    def complete_json(self, prompt: str, images: list[bytes] | None = None, max_tokens: int = 2000) -> dict[str, Any]:
        try:
            if self.provider == "claude":
                import anthropic  # lazy, optional

                client = anthropic.Anthropic(api_key=self.api_key)
                content: list[dict[str, Any]] = [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                 "data": base64.b64encode(img).decode()}}
                    for img in images or []
                ]
                content.append({"type": "text", "text": prompt})
                msg = client.messages.create(
                    model=self.model, max_tokens=max_tokens, system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": content}],
                )
                text = "".join(getattr(b, "text", "") for b in msg.content)
            else:
                from google import genai  # lazy, optional
                from google.genai import types

                client = genai.Client(api_key=self.api_key)
                parts: list[Any] = [types.Part.from_bytes(data=img, mime_type="image/jpeg") for img in images or []]
                parts.append(prompt)
                resp = client.models.generate_content(
                    model=self.model, contents=parts,
                    config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT,
                                                       response_mime_type="application/json"),
                )
                text = resp.text or ""
        except AdapterError:
            raise
        except Exception as exc:  # noqa: BLE001 - network/auth/SDK errors become a failed step
            raise AdapterError(f"{self.provider} call failed: {type(exc).__name__}: {str(exc)[:160]}") from exc
        return _extract_json(text)


class ProviderLLM(LLMAdapter):
    mode = "real"

    def __init__(self, client: LLMClient):
        self.client = client
        self.provider = client.provider
        self.model = client.model

    def availability(self) -> Availability:
        return self.client.availability()

    def describe_segments(self, segments: list[dict[str, Any]], pcs: list[dict[str, Any]]) -> LLMResult:
        prompt = (
            "Performance Criteria (verbatim):\n"
            + "\n".join(f"- {p['code']}: {p['text']}" for p in pcs)
            + "\n\nEvidence segments (time in seconds, transcript and visual tags where available):\n"
            + json.dumps(segments, ensure_ascii=False)
            + '\n\nReturn JSON: {"descriptions":[{"start_s":number,"end_s":number,"description":"one neutral '
              'sentence of what is observable"}],"summary":"two neutral sentences describing the whole recording"}. '
              "Only include segments with observable content."
        )
        data = self.client.complete_json(prompt)
        descs = [
            SegmentDescription(float(d["start_s"]), float(d["end_s"]), str(d["description"]))
            for d in data.get("descriptions", []) if isinstance(d, dict) and "description" in d
        ]
        return LLMResult(self.provider, self.model, "real", descs, data.get("summary"))


class UnavailableLLM(LLMAdapter):
    provider = "none"
    model = ""
    mode = "unavailable"

    def __init__(self, reason: str):
        self.reason = reason

    def availability(self) -> Availability:
        return Availability(False, self.reason)

    def describe_segments(self, segments, pcs) -> LLMResult:  # pragma: no cover - never called
        raise AdapterError(self.reason)


class DemoLLM(LLMAdapter):
    provider = DEMO_PROVIDER
    model = DEMO_MODEL
    mode = "demo"

    def __init__(self, demo: DemoProvider):
        self.demo = demo

    def availability(self) -> Availability:
        return Availability(True, "Seeded descriptions for the demo asset only (matched by SHA-256).")

    def describe_segments(self, segments, pcs) -> LLMResult:
        fx = self.demo.fixture
        descs = [SegmentDescription(float(d["start_s"]), float(d["end_s"]), d["description"])
                 for d in fx.get("segment_descriptions", [])]
        return LLMResult(self.provider, self.model, "demo", descs, fx.get("summary"))
