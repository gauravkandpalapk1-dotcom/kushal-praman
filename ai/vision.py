"""Vision tag adapters (objects / actions per segment).

LLMVision extracts one keyframe per segment with ffmpeg and asks a vision-capable LLM for neutral
object/action tags. It is available only when an API key is configured. DemoVision returns the
seeded tags for the demo asset only.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from ai.base import AdapterError, Availability, SegmentTags, TimeSpan, VisionAdapter, VisionResult
from ai.demo_provider import MODEL as DEMO_MODEL
from ai.demo_provider import PROVIDER as DEMO_PROVIDER
from ai.demo_provider import DemoProvider
from ai.llm import LLMClient
from ai.segmentation import MediaToolError, extract_keyframe

MAX_FRAMES = 12


class LLMVision(VisionAdapter):
    mode = "real"

    def __init__(self, client: LLMClient):
        self.client = client
        self.provider = f"{client.provider}-vision"
        self.model = client.model

    def availability(self) -> Availability:
        return self.client.availability()

    def describe(self, path: Path, *, kind: str, spans: list[TimeSpan]) -> VisionResult:
        if kind == "photo":
            images, used = [path.read_bytes()], [TimeSpan(0.0, 0.0)]
        else:
            images, used = [], []
            with tempfile.TemporaryDirectory(prefix="kp_frames_") as tmp:
                for i, span in enumerate(spans[:MAX_FRAMES]):
                    mid = span.start_s + (span.end_s - span.start_s) / 2
                    try:
                        frame = extract_keyframe(path, mid, Path(tmp) / f"f{i}.jpg")
                    except MediaToolError:
                        continue
                    images.append(frame.read_bytes())
                    used.append(span)
        if not images:
            raise AdapterError("No keyframes could be extracted.")
        prompt = (
            f"There are {len(images)} images in order (index 0..{len(images) - 1}). For each, list up to 8 short, "
            "neutral tags naming visible tools, materials, equipment and actions (e.g. 'wire stripper', "
            "'crimping lug'). No judgements. Return JSON: {\"frames\":[{\"index\":0,\"tags\":[\"...\"]}]}"
        )
        data = self.client.complete_json(prompt, images=images, max_tokens=1500)
        by_index = {int(f.get("index", -1)): f.get("tags", []) for f in data.get("frames", []) if isinstance(f, dict)}
        tags = [SegmentTags(s.start_s, s.end_s, [str(t) for t in by_index.get(i, [])][:8]) for i, s in enumerate(used)]
        return VisionResult(self.provider, self.model, "real", tags)


class UnavailableVision(VisionAdapter):
    provider = "none"
    model = ""
    mode = "unavailable"

    def __init__(self, reason: str):
        self.reason = reason

    def availability(self) -> Availability:
        return Availability(False, self.reason)

    def describe(self, path, *, kind, spans) -> VisionResult:  # pragma: no cover - never called
        raise AdapterError(self.reason)


class DemoVision(VisionAdapter):
    provider = DEMO_PROVIDER
    model = DEMO_MODEL
    mode = "demo"

    def __init__(self, demo: DemoProvider):
        self.demo = demo

    def availability(self) -> Availability:
        return Availability(True, "Seeded tags for the demo asset only (matched by SHA-256).")

    def describe(self, path: Path, *, kind: str, spans: list[TimeSpan]) -> VisionResult:
        tags = [SegmentTags(float(t["start_s"]), float(t["end_s"]), list(t["tags"]))
                for t in self.demo.fixture.get("vision_tags", [])]
        return VisionResult(self.provider, self.model, "demo", tags)
