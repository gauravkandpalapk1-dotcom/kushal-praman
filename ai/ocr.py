"""OCR adapters (photos / documents only).

TesseractOCR needs both the `pytesseract` package and the `tesseract` binary; otherwise it is
reported unavailable. DemoOCR serves fixture OCR text only for a demo asset that has one (the
bundled demo asset is a video, so in practice OCR is "not applicable" in the demo).
"""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

from ai.base import AdapterError, Availability, OCRAdapter, OCRResult
from ai.demo_provider import MODEL as DEMO_MODEL
from ai.demo_provider import PROVIDER as DEMO_PROVIDER
from ai.demo_provider import DemoProvider


class TesseractOCR(OCRAdapter):
    provider = "tesseract"
    model = "tesseract (eng+hin)"
    mode = "real"

    def __init__(self, enabled: bool = True):
        self._enabled = enabled

    def availability(self) -> Availability:
        if not self._enabled:
            return Availability(False, "OCR disabled (OCR_PROVIDER=none).")
        if importlib.util.find_spec("pytesseract") is None:
            return Availability(False, "pytesseract is not installed.")
        if not shutil.which("tesseract"):
            return Availability(False, "Tesseract binary not found on PATH.")
        return Availability(True, "Tesseract OCR (local).")

    def extract(self, path: Path, *, mime_type: str) -> OCRResult:
        if mime_type == "application/pdf":
            raise AdapterError("PDF rasterisation is not available in this build; OCR runs on images only.")
        try:
            import pytesseract  # lazy, optional
            from PIL import Image

            with Image.open(path) as img:
                try:
                    text = pytesseract.image_to_string(img, lang="eng+hin")
                except pytesseract.TesseractError:
                    text = pytesseract.image_to_string(img, lang="eng")
        except AdapterError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"Tesseract failed: {type(exc).__name__}: {str(exc)[:160]}") from exc
        return OCRResult(self.provider, self.model, "real", text.strip())


class DemoOCR(OCRAdapter):
    provider = DEMO_PROVIDER
    model = DEMO_MODEL
    mode = "demo"

    def __init__(self, demo: DemoProvider):
        self.demo = demo

    def availability(self) -> Availability:
        has = "ocr" in self.demo.fixture
        return Availability(has, "Seeded OCR text for the demo asset." if has else "Demo asset has no OCR fixture (it is a video).")

    def extract(self, path: Path, *, mime_type: str) -> OCRResult:
        return OCRResult(self.provider, self.model, "demo", str(self.demo.fixture.get("ocr", "")))
