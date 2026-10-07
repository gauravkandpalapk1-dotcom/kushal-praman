"""Brute-force protection for /auth/login.

Sliding window per (email, client IP): after MAX_FAILURES failed attempts within WINDOW_S seconds,
further attempts get HTTP 429 until the oldest failure leaves the window. A successful login clears
the counter. In-memory and single-process, matching the single-process demo deployment; a shared
deployment would back this with Redis.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

MAX_FAILURES = 8
WINDOW_S = 600.0

_failures: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def _key(email: str, ip: str) -> tuple[str, str]:
    return email.strip().lower(), ip or "unknown"


def _prune(q: deque[float], now: float) -> None:
    while q and now - q[0] > WINDOW_S:
        q.popleft()


def retry_after(email: str, ip: str, now: float | None = None) -> int:
    """Seconds until another attempt is allowed (0 = allowed now)."""
    now = time.monotonic() if now is None else now
    with _lock:
        q = _failures.get(_key(email, ip))
        if not q:
            return 0
        _prune(q, now)
        if len(q) < MAX_FAILURES:
            return 0
        return max(1, int(WINDOW_S - (now - q[0])) + 1)


def record_failure(email: str, ip: str, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    with _lock:
        q = _failures[_key(email, ip)]
        _prune(q, now)
        q.append(now)


def record_success(email: str, ip: str) -> None:
    with _lock:
        _failures.pop(_key(email, ip), None)


def reset() -> None:
    """Test hook."""
    with _lock:
        _failures.clear()
