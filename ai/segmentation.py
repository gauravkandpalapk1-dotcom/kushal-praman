"""REAL media probing and segmentation with ffprobe/ffmpeg (no demo path here).

Segmentation = ffmpeg scene-change detection (`select='gt(scene,T)',showinfo`, cut times parsed
from `pts_time`), falling back to fixed windows when no cut is found. Segments are contiguous and
cover [0, duration].
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

_PTS = re.compile(r"pts_time:\s*([0-9]+(?:\.[0-9]+)?)")
MIN_SEGMENT_S = 1.0


class MediaToolError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def ffmpeg_info() -> dict[str, Any]:
    """{"available", "version", "ffprobe"} for /health."""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    version = None
    if ffmpeg:
        try:
            out = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, timeout=10).stdout
            m = re.match(r"ffmpeg version (\S+)", out)
            version = m.group(1) if m else out.splitlines()[0][:80]
        except (OSError, subprocess.SubprocessError):
            ffmpeg = None
    return {"available": bool(ffmpeg), "version": version, "ffprobe": bool(ffprobe)}


@dataclass
class ProbeResult:
    duration_s: float | None
    width: int | None
    height: int | None
    video_codec: str | None
    audio_codec: str | None
    has_video: bool
    has_audio: bool
    format_name: str | None
    bit_rate: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Segment:
    start_s: float
    end_s: float
    label: str
    source: str  # scene | window | whole


@dataclass
class SegmentationResult:
    method: str  # scene | window | whole
    threshold: float | None
    cuts: list[float]
    segments: list[Segment] = field(default_factory=list)
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def probe(path: Path, timeout: int = 60) -> ProbeResult:
    exe = shutil.which("ffprobe")
    if not exe:
        raise MediaToolError("ffprobe not found on PATH")
    proc = subprocess.run(
        [exe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise MediaToolError(f"ffprobe failed: {proc.stderr.strip()[:200]}")
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams", [])
    fmt = data.get("format", {})
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = fmt.get("duration") or (video or {}).get("duration") or (audio or {}).get("duration")
    try:
        duration_f = round(float(duration), 3) if duration not in (None, "N/A") else None
    except ValueError:
        duration_f = None
    br = fmt.get("bit_rate")
    return ProbeResult(
        duration_s=duration_f,
        width=int(video["width"]) if video and video.get("width") else None,
        height=int(video["height"]) if video and video.get("height") else None,
        video_codec=video.get("codec_name") if video else None,
        audio_codec=audio.get("codec_name") if audio else None,
        has_video=video is not None,
        has_audio=audio is not None,
        format_name=fmt.get("format_name"),
        bit_rate=int(br) if br and str(br).isdigit() else None,
    )


def detect_scenes(path: Path, threshold: float = 0.15, timeout: int = 900) -> list[float]:
    """Scene-change timestamps (seconds) from ffmpeg's scene score."""
    exe = shutil.which("ffmpeg")
    if not exe:
        raise MediaToolError("ffmpeg not found on PATH")
    proc = subprocess.run(
        [exe, "-hide_banner", "-nostats", "-i", str(path), "-an", "-sn", "-dn",
         "-vf", f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise MediaToolError(f"ffmpeg scene detection failed: {proc.stderr.strip()[-200:]}")
    return sorted({round(float(m.group(1)), 3) for m in _PTS.finditer(proc.stderr)})


def build_segments(duration: float, cuts: list[float], *, source: str = "scene", label: str = "Scene",
                   min_len: float = MIN_SEGMENT_S) -> list[Segment]:
    """Contiguous segments [0,c1),[c1,c2)...[cn,duration]; cuts closer than min_len are merged."""
    bounds = [0.0]
    for c in sorted(cuts):
        if min_len <= c <= duration - min_len and c - bounds[-1] >= min_len:
            bounds.append(c)
    bounds.append(duration)
    return [Segment(round(a, 3), round(b, 3), f"{label} {i + 1}", source) for i, (a, b) in enumerate(zip(bounds, bounds[1:]))]


def fixed_windows(duration: float, window: float = 30.0) -> list[Segment]:
    cuts, t = [], window
    while t < duration:
        cuts.append(t)
        t += window
    return build_segments(duration, cuts, source="window", label="Window")


def segment_media(path: Path, *, kind: str, duration: float | None, has_video: bool,
                  threshold: float = 0.15, window: float = 30.0) -> SegmentationResult:
    if kind in ("photo", "document") or not duration:
        seg = Segment(0.0, float(duration or 0.0), "Whole item", "whole")
        return SegmentationResult("whole", None, [], [seg], "Still item: one segment covering the whole evidence.")
    if has_video:
        cuts = detect_scenes(path, threshold)
        segments = build_segments(duration, cuts)
        if len(segments) > 1:
            return SegmentationResult(
                "scene", threshold, cuts, segments,
                f"ffmpeg scene detection (threshold {threshold}): {len(cuts)} cuts → {len(segments)} segments.",
            )
        windows = fixed_windows(duration, window)
        return SegmentationResult(
            "window", threshold, cuts, windows,
            f"No scene cuts above threshold {threshold}; fell back to fixed {int(window)} s windows ({len(windows)} segments).",
        )
    windows = fixed_windows(duration, window)
    return SegmentationResult("window", None, [], windows, f"Audio-only: fixed {int(window)} s windows ({len(windows)} segments).")


def extract_keyframe(path: Path, at_s: float, out: Path, timeout: int = 60) -> Path:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise MediaToolError("ffmpeg not found on PATH")
    proc = subprocess.run(
        [exe, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{at_s:.3f}", "-i", str(path),
         "-frames:v", "1", "-vf", "scale='min(768,iw)':-2", str(out)],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0 or not out.exists():
        raise MediaToolError(f"keyframe extraction failed at {at_s:.1f}s")
    return out
