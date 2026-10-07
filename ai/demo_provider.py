"""DEMO provider: deterministic seeded analysis for ONE known asset, matched by SHA-256.

The fixture (ai/fixtures/practical_demo.json) is used only when the uploaded file's server-side
SHA-256 equals the SHA-256 of storage/demo/practical_demo.mp4 computed at startup. Any other
upload never sees fixture data. Everything returned from here is labelled mode="demo".
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "practical_demo.json"
PROVIDER = "demo"
MODEL = "seeded fixture"


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


class DemoProvider:
    def __init__(self, asset_path: Path, fixture_path: Path = FIXTURE_PATH):
        self.asset_path = Path(asset_path)
        self.fixture_path = Path(fixture_path)
        self._sha: str | None = None
        self._fixture: dict[str, Any] | None = None
        self._lock = threading.Lock()

    @property
    def asset_available(self) -> bool:
        return self.asset_path.is_file()

    @property
    def asset_sha256(self) -> str | None:
        with self._lock:
            if self._sha is None and self.asset_available:
                self._sha = sha256_file(self.asset_path)
            return self._sha

    @property
    def fixture(self) -> dict[str, Any]:
        with self._lock:
            if self._fixture is None:
                self._fixture = json.loads(self.fixture_path.read_text(encoding="utf-8"))
            return self._fixture

    def is_demo_asset(self, sha256: str | None) -> bool:
        return bool(sha256) and sha256.lower() == (self.asset_sha256 or "")


_provider: DemoProvider | None = None
_plock = threading.Lock()


def get_demo_provider(asset_path: Path | None = None) -> DemoProvider:
    """Process-wide provider. The first call fixes the asset path (from settings)."""
    global _provider
    with _plock:
        if _provider is None or (asset_path is not None and Path(asset_path) != _provider.asset_path):
            if asset_path is None:
                raise RuntimeError("Demo provider not initialised; pass asset_path on first call")
            _provider = DemoProvider(Path(asset_path))
        return _provider


def is_demo_asset(sha256: str | None) -> bool:
    return _provider is not None and _provider.is_demo_asset(sha256)
