"""Non-demo media: real services only; unavailable services are skipped, never faked."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
import uuid

import pytest

API = "/api/v1"
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg missing")


def _make_video(path, seconds=8):
    # two colour sections -> one real scene cut at 4 s; with a sine audio track
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"color=c=red:s=160x120:d={seconds // 2}:r=10",
                    "-f", "lavfi", "-i", f"color=c=blue:s=160x120:d={seconds // 2}:r=10",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                    "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2:a",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)
    return path.read_bytes()


def _wait(client, ev_id, h):
    for _ in range(300):
        p = client.get(f"{API}/evidence/{ev_id}/processing", headers=h).json()
        if p["status"] in ("done", "failed"):
            return p
        time.sleep(0.2)
    raise AssertionError("timeout")


def test_non_demo_video_uses_only_real_services(client, fresh, tmp_path):
    content = _make_video(tmp_path / "clip.mp4")
    meta = {"local_id": str(uuid.uuid4()), "kind": "video", "client_sha256": hashlib.sha256(content).hexdigest()}
    ev = client.post(f"{API}/evidence", headers=fresh["raj"], files={"file": ("clip.mp4", content, "video/mp4")},
                     data={"meta": json.dumps(meta)}).json()
    assert ev["is_demo"] is False
    assert client.post(f"{API}/evidence/{ev['id']}/process", headers=fresh["a07"]).status_code == 202
    p = _wait(client, ev["id"], fresh["a07"])
    assert p["status"] == "done" and p["mode"] == "real", p
    steps = {s["key"]: s for s in p["steps"]}
    assert all(s["mode"] != "demo" for s in p["steps"])
    assert steps["segmentation"]["status"] == "done"
    for key in ("speech", "vision", "llm"):
        assert steps[key]["status"] == "skipped" and steps[key]["mode"] == "unavailable", steps[key]
    assert steps["ocr"]["status"] == "skipped"
    assert steps["mapping"]["status"] == "done" and "0 links" in steps["mapping"]["detail"]
    ws = client.get(f"{API}/evidence/{ev['id']}/workspace", headers=fresh["a07"]).json()
    assert ws["transcript"] == [] and ws["surfaced"] == []
    assert any(abs(s["start_s"] - 4) < 0.6 for s in ws["segments"])  # real scene cut
    # forced re-run creates a new run
    r = client.post(f"{API}/evidence/{ev['id']}/process?force=true", headers=fresh["a07"]).json()
    assert r["run"] == p["run"] + 1
    assert _wait(client, ev["id"], fresh["a07"])["status"] == "done"


def test_photo_pipeline(client, fresh):
    png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
           b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82")
    meta = {"local_id": str(uuid.uuid4()), "kind": "photo", "client_sha256": hashlib.sha256(png).hexdigest()}
    ev = client.post(f"{API}/evidence", headers=fresh["raj"], files={"file": ("p.png", png, "image/png")},
                     data={"meta": json.dumps(meta)}).json()
    client.post(f"{API}/evidence/{ev['id']}/process", headers=fresh["admin"])
    p = _wait(client, ev["id"], fresh["admin"])
    steps = {s["key"]: s for s in p["steps"]}
    assert p["status"] == "done"
    assert steps["speech"]["status"] == "skipped" and "not applicable" in steps["speech"]["detail"].lower()
    assert steps["ocr"]["status"] == "skipped" and steps["ocr"]["mode"] == "unavailable"
    assert steps["segmentation"]["detail"].startswith("Still item")
