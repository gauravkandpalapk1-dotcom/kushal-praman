"""Generate the SYNTHETIC 10:00 demo practical recording with ffmpeg.

This is placeholder media, watermarked as synthetic. It exists so the demo works with no
external assets. Replace storage/demo/practical_demo.mp4 with a real recorded practical
(see docs/DEMO.md) before any presentation where real footage is expected.

Each section has its own background colour, so ffmpeg scene detection finds real cuts at the
section boundaries (00:42 and 01:08 included).

Usage:  python scripts/make_demo_video.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "storage" / "demo" / "practical_demo.mp4"

DURATION = 600  # 10:00
SECTIONS = [
    # (start, end, colour, caption)
    (0, 42, "0x1B2340", "Work area preparation - PPE check - supply isolation verified"),
    (42, 68, "0xA8701A", "Stripping insulation with insulated wire stripper - crimping lug - terminating at panel"),
    (68, 210, "0x16303F", "Routing cables through panel trunking"),
    (210, 360, "0x5B7A3C", "Mounting MCB and contactor on DIN rail"),
    (360, 510, "0x221A2E", "Continuity check with multimeter"),
    (510, 600, "0x5A5A5A", "Housekeeping - tools returned - area cleared"),
]


def _font() -> str:
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            # ffmpeg filter syntax needs the drive colon escaped
            return c.replace(":", "\\:")
    sys.exit("No usable TTF font found; edit _font() in this script.")


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("ffmpeg not found on PATH")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    font = _font()

    filters = []
    for start, end, colour, caption in SECTIONS:
        en = f"between(t\\,{start}\\,{end - 0.001})"
        filters.append(f"drawbox=x=0:y=0:w=iw:h=ih:color={colour}:t=fill:enable='{en}'")
        filters.append(
            f"drawtext=fontfile='{font}':text='{caption}':fontcolor=0xF6F1E7:fontsize=17:"
            f"x=(w-tw)/2:y=h/2-10:enable='{en}'"
        )
    filters += [
        f"drawtext=fontfile='{font}':text='SYNTHETIC DEMO MEDIA - replace with a real recorded practical':"
        "fontcolor=0xF5A524:fontsize=14:x=12:y=12",
        f"drawtext=fontfile='{font}':text='Assistant Electrician - practical demonstration':"
        "fontcolor=0xC9C3B6:fontsize=13:x=12:y=h-28",
        f"drawtext=fontfile='{font}':text='%{{pts\\:hms}}':fontcolor=0xF6F1E7:fontsize=20:x=w-tw-12:y=h-34",
    ]

    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c=black:s=640x360:r=5:d={DURATION}",
        "-f", "lavfi", "-i", f"anullsrc=r=16000:cl=mono",
        "-t", str(DURATION),
        "-vf", ",".join(filters),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "34", "-pix_fmt", "yuv420p", "-g", "10",
        "-c:a", "aac", "-b:a", "24k",
        "-movflags", "+faststart",
        str(OUT),
    ]
    subprocess.run(cmd, check=True)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
