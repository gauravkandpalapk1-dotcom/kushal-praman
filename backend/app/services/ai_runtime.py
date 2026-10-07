"""Process-wide access to the AI adapter registry and the demo provider."""
from __future__ import annotations

import threading

from ai.demo_provider import DemoProvider, get_demo_provider
from ai.registry import Registry
from backend.app.config import get_settings

_registry: Registry | None = None
_lock = threading.Lock()


def demo_provider() -> DemoProvider:
    return get_demo_provider(get_settings().DEMO_ASSET_PATH)


def registry() -> Registry:
    global _registry
    with _lock:
        if _registry is None:
            _registry = Registry(get_settings(), demo_provider())
        return _registry


def reset() -> None:
    global _registry
    with _lock:
        _registry = None


def is_demo_asset(sha256: str) -> bool:
    return demo_provider().is_demo_asset(sha256)
