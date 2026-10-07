"""File streaming with HTTP Range support (206 Partial Content) so <video> seeking works."""
from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

from fastapi.responses import Response, StreamingResponse

from backend.app.errors import NotFound, RangeNotSatisfiable

CHUNK = 256 * 1024
_RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _iter_file(path: Path, start: int, length: int) -> Iterator[bytes]:
    with open(path, "rb") as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            chunk = f.read(min(CHUNK, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    """Return inclusive (start, end) or None for a full response. Multi-range requests get the full body."""
    if not header:
        return None
    header = header.strip()
    if "," in header:
        return None
    m = _RANGE.match(header)
    if not m or (m.group(1) == "" and m.group(2) == ""):
        raise RangeNotSatisfiable("Malformed Range header.")
    first, last = m.group(1), m.group(2)
    if first == "":  # suffix: last N bytes
        n = int(last)
        if n == 0:
            raise RangeNotSatisfiable("Empty suffix range.")
        return max(0, size - n), size - 1
    start = int(first)
    end = int(last) if last else size - 1
    if start >= size or end < start:
        raise RangeNotSatisfiable(f"Range not satisfiable for {size} bytes.")
    return start, min(end, size - 1)


def file_response(path: Path, media_type: str, range_header: str | None, *, filename: str | None = None) -> Response:
    if not path.is_file():
        raise NotFound("Media file not found.", "media_missing")
    size = os.path.getsize(path)
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=600",
               "X-Content-Type-Options": "nosniff"}
    if filename:
        headers["Content-Disposition"] = f'inline; filename="{filename}"'
    try:
        rng = parse_range(range_header, size)
    except RangeNotSatisfiable:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}", **headers})
    if rng is None:
        headers["Content-Length"] = str(size)
        return StreamingResponse(_iter_file(path, 0, size), media_type=media_type, headers=headers)
    start, end = rng
    length = end - start + 1
    headers.update({"Content-Range": f"bytes {start}-{end}/{size}", "Content-Length": str(length)})
    return StreamingResponse(_iter_file(path, start, length), status_code=206, media_type=media_type, headers=headers)
