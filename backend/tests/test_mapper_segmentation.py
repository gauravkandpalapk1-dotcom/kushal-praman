"""Mapper formatting/ranking on the demo fixture, and real ffmpeg segmentation on the demo video."""
from __future__ import annotations

import json
import shutil

import pytest

from ai import mapper
from ai.demo_provider import FIXTURE_PATH
from ai.segmentation import build_segments, detect_scenes, fixed_windows, probe, segment_media
from backend.app.config import ROOT

DEMO_VIDEO = ROOT / "storage" / "demo" / "practical_demo.mp4"
QP = json.loads((ROOT / "database" / "seed" / "qualification_assistant_electrician.json").read_text(encoding="utf-8"))
PC10 = next(pc for n in QP["nos"] for pc in n["pcs"] if pc["code"] == "PC10")


def test_format_and_statement():
    assert mapper.format_ts(42) == "00:42"
    assert mapper.format_ts(68) == "01:08"
    assert mapper.format_ts(600) == "10:00"
    assert mapper.statement("PC10", 42, 68) == "Potential evidence supporting PC10 found at 00:42–01:08."


def test_stemming():
    assert mapper.stem("stripping") == mapper.stem("strip") == mapper.stem("strips")
    assert mapper.stem("crimping") == mapper.stem("crimp")


def _fixture_segments():
    fx = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    bounds = [0, 42, 68, 210, 360, 510, 600]
    segs = []
    for a, b in zip(bounds, bounds[1:]):
        lines = [t for t in fx["transcript"] if a <= (t["start_s"] + t["end_s"]) / 2 < b]
        tags = [tag for v in fx["vision_tags"] if v["start_s"] == a for tag in v["tags"]]
        desc = " ".join(d["description"] for d in fx["segment_descriptions"] if d["start_s"] == a)
        segs.append(mapper.SegmentText(a, b, " ".join(f"{t['text']} {t['translation_en']}" for t in lines), tags, desc))
    return segs


def test_ranking_on_fixture_puts_42_68_first_for_pc10():
    pc = mapper.PCSpec(1, "PC10", PC10["text"], PC10["keywords"], "ISC/N1002")
    ranked = mapper.rank(_fixture_segments(), [pc])["PC10"]
    top = ranked[0]
    assert (top.start_s, top.end_s) == (42, 68)
    assert 0 < top.score < 1
    assert top.score > ranked[1].score + 0.3
    assert "crimping tool" in top.matched_keywords
    assert top.statement == "Potential evidence supporting PC10 found at 00:42–01:08."
    proposals = mapper.propose(_fixture_segments(), [pc])
    assert len(proposals) == 1 and proposals[0].start_s == 42
    assert "not a probability" in proposals[0].rationale()


def test_per_segment_ranking_shape():
    pc = mapper.PCSpec(1, "PC10", PC10["text"], PC10["keywords"])
    per = mapper.rank_per_segment(_fixture_segments(), [pc])
    assert len(per) == 6 and per[1]["pcs"][0]["pc_code"] == "PC10"


def test_build_segments_contiguous():
    segs = build_segments(600, [42, 68, 210, 360, 510])
    assert [(s.start_s, s.end_s) for s in segs] == [(0, 42), (42, 68), (68, 210), (210, 360), (360, 510), (510, 600)]
    w = fixed_windows(70, 30)
    assert [(s.start_s, s.end_s) for s in w] == [(0, 30), (30, 60), (60, 70)]


needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg") or not DEMO_VIDEO.exists(), reason="ffmpeg/demo video missing")


@needs_ffmpeg
def test_real_scene_detection_on_demo_video():
    p = probe(DEMO_VIDEO)
    assert p.duration_s == pytest.approx(600, abs=0.5)
    cuts = detect_scenes(DEMO_VIDEO, 0.15)
    assert any(abs(c - 42) < 1 for c in cuts)
    assert any(abs(c - 68) < 1 for c in cuts)
    res = segment_media(DEMO_VIDEO, kind="video", duration=p.duration_s, has_video=p.has_video)
    assert res.method == "scene"
    assert any(abs(s.start_s - 42) < 1 and abs(s.end_s - 68) < 1 for s in res.segments)
    assert res.segments[0].start_s == 0 and res.segments[-1].end_s == pytest.approx(600, abs=0.5)
