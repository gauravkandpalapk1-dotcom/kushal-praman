"""End-to-end jury flow through the HTTP API, plus demo reset to every stage."""
from __future__ import annotations

import hashlib
import json
import time
import uuid

import pytest

from backend.tests.conftest import DEMO_VIDEO, login

API = "/api/v1"


def _wait_done(client, ev_id, headers, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        p = client.get(f"{API}/evidence/{ev_id}/processing", headers=headers).json()
        if p["status"] in ("done", "failed"):
            return p
        time.sleep(0.3)
    raise AssertionError("pipeline did not finish")


def _pc10_id(client, headers):
    tree = client.get(f"{API}/qualifications/1/tree", headers=headers).json()
    return next(pc["id"] for n in tree["nos"] for pc in n["pcs"] if pc["code"] == "PC10")


def test_full_assessor_first_flow(client, fresh):
    raj, a07, a12, admin = fresh["raj"], fresh["a07"], fresh["a12"], fresh["admin"]
    content = DEMO_VIDEO.read_bytes()
    meta = {"local_id": str(uuid.uuid4()), "kind": "video", "qualification_id": 1,
            "client_sha256": hashlib.sha256(content).hexdigest(), "captured_at": "2026-10-07T09:02:11Z",
            "latitude": 30.3165, "longitude": 78.0322, "accuracy_m": 12, "language": "hi",
            "encrypted_at_rest": True, "offline_captured": True, "sync_attempts": 2}
    r = client.post(f"{API}/evidence", headers=raj, files={"file": ("practical.mp4", content, "video/mp4")},
                    data={"meta": json.dumps(meta)})
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["label"] == "Evidence #17" and ev["is_demo"] and ev["integrity_ok"]
    ev_id = ev["id"]

    # candidates cannot trigger processing
    assert client.post(f"{API}/evidence/{ev_id}/process", headers=raj).status_code == 403
    p = client.post(f"{API}/evidence/{ev_id}/process", headers=a07)
    assert p.status_code == 202
    assert [s["key"] for s in p.json()["steps"]] == ["integrity", "probe", "segmentation", "speech", "vision", "ocr",
                                                    "llm", "mapping"]
    done = _wait_done(client, ev_id, a07)
    assert done["status"] == "done" and done["mode"] == "demo", done
    steps = {s["key"]: s for s in done["steps"]}
    assert steps["integrity"]["mode"] == "real" and steps["probe"]["mode"] == "real"
    assert steps["segmentation"]["mode"] == "real" and steps["segmentation"]["status"] == "done"
    assert steps["speech"]["mode"] == "demo" and steps["mapping"]["mode"] == "demo"
    assert steps["ocr"]["status"] == "skipped" and "not applicable" in steps["ocr"]["detail"].lower()
    # re-POST without force returns the current job
    again = client.post(f"{API}/evidence/{ev_id}/process", headers=a07).json()
    assert again["run"] == done["run"] and again["status"] == "done"
    assert client.get(f"{API}/evidence/{ev_id}", headers=raj).json()["status"] == "ready"

    # workspace: tier 1 only
    ws = client.get(f"{API}/evidence/{ev_id}/workspace", headers=a07).json()
    assert ws["evidence"]["metadata"]["duration_s"] == pytest.approx(600, abs=0.5)
    assert any(abs(s["start_s"] - 42) < 1 and abs(s["end_s"] - 68) < 1 for s in ws["segments"])
    assert len(ws["transcript"]) == 8 and ws["transcript"][0]["mode"] == "demo"
    surfaced = [s for s in ws["surfaced"] if s["pc_code"] == "PC10"]
    assert len(surfaced) == 1
    s10 = surfaced[0]
    assert (s10["start_s"], s10["end_s"]) == (42, 68) and s10["nos_code"] == "ISC/N1002"
    assert s10["statement"] == "Potential evidence supporting PC10 found at 00:42–01:08."
    assert "confidence" not in json.dumps(ws)
    assert client.get(f"{API}/evidence/{ev_id}/workspace", headers=raj).status_code == 403

    pc10 = _pc10_id(client, a07)
    mapping_id = s10["mapping_id"]
    # tier gating before lock
    m_a07 = client.get(f"{API}/evidence/{ev_id}/mappings", headers=a07).json()[0]
    assert m_a07["locked"] and m_a07["confidence"] is None and m_a07["rationale"] is None and m_a07["tags"] is None
    m_admin = client.get(f"{API}/evidence/{ev_id}/mappings", headers=admin).json()[0]
    assert m_admin["locked"] is False and m_admin["confidence"] == 0.91
    m_raj = client.get(f"{API}/evidence/{ev_id}/mappings", headers=raj).json()[0]
    assert m_raj["locked"] and m_raj["confidence"] is None

    # A-07 opens PC10
    r = client.post(f"{API}/assessments", json={"evidence_id": ev_id, "pc_id": pc10}, headers=a07)
    assert r.status_code == 201
    a = r.json()
    aid = a["id"]
    assert a["status"] == "opened" and a["max_score"] == 4 and a["is_second_assessor"] is False
    assert a["pc"]["rubric"]["status"] == "draft" and len(a["pc"]["rubric"]["levels"]) == 5
    assert client.post(f"{API}/assessments", json={"evidence_id": ev_id, "pc_id": pc10}, headers=a07).status_code == 200

    r = client.get(f"{API}/assessments/{aid}/ai-support", headers=a07)
    assert r.status_code == 409 and r.json()["code"] == "initial_score_required"
    r = client.post(f"{API}/mappings/{mapping_id}/confirm", json={}, headers=a07)
    assert r.status_code == 409
    assert client.post(f"{API}/assessments/{aid}/final", json={"score": 3}, headers=a07).status_code == 409
    assert client.post(f"{API}/assessments/{aid}/initial", json={"score": 5}, headers=a07).status_code == 422
    assert client.post(f"{API}/assessments/{aid}/initial", json={"score": 3}, headers=a12).status_code == 403

    r = client.post(f"{API}/assessments/{aid}/initial", json={"score": 3, "note": "Clean strip and crimp."}, headers=a07)
    assert r.status_code == 200 and r.json()["status"] == "initial_locked" and r.json()["initial_score"] == 3
    r = client.post(f"{API}/assessments/{aid}/initial", json={"score": 4}, headers=a07)
    assert r.status_code == 409 and r.json()["code"] == "initial_already_locked"

    r = client.get(f"{API}/assessments/{aid}/ai-support", headers=a07)
    assert r.status_code == 200, r.text
    sup = r.json()
    assert sup["mode"] == "demo"
    f0 = sup["findings"][0]
    assert f0["confidence"] == 0.91 and f0["signal"] == "supports" and (f0["start_s"], f0["end_s"]) == (42, 68)
    assert len(f0["transcript"]) == 3 and sup["disclaimer"].startswith("AI output identifies")
    assert client.get(f"{API}/assessments/{aid}", headers=a07).json()["status"] == "ai_revealed"
    assert client.get(f"{API}/evidence/{ev_id}/mappings", headers=a07).json()[0]["confidence"] == 0.91

    assert client.post(f"{API}/mappings/{mapping_id}/reject", json={"reason": ""}, headers=a07).status_code == 422
    r = client.post(f"{API}/mappings/{mapping_id}/confirm", json={}, headers=a07)
    assert r.status_code == 200 and r.json()["status"] == "confirmed" and r.json()["decided_by"] == "A-07"

    r = client.post(f"{API}/assessments/{aid}/final", json={"score": 2}, headers=a07)
    assert r.status_code == 422 and r.json()["code"] == "rationale_required"
    r = client.post(f"{API}/assessments/{aid}/final", json={"score": 3}, headers=a07)
    assert r.status_code == 200
    fa = r.json()
    assert fa["status"] == "finalized" and fa["final_score"] == 3 and fa["score_changed"] is False
    assert client.post(f"{API}/assessments/{aid}/final", json={"score": 3}, headers=a07).status_code == 409

    v = client.get(f"{API}/audit/verify", headers=a07).json()
    assert v["ok"] is True and v["broken_at"] is None
    trail = client.get(f"{API}/assessments/{aid}/audit", headers=a07).json()
    actions = [e["action"] for e in trail]
    for needed in ("evidence.received", "evidence.integrity_verified", "processing.started", "processing.completed",
                   "mapping.proposed", "assessment.opened", "assessment.initial_locked", "ai.revealed",
                   "mapping.confirmed", "assessment.finalized"):
        assert needed in actions, needed
    summaries = [e["summary"] for e in trail]
    assert "Initial score 3/4 locked for PC10" in summaries
    assert "AI evidence revealed to A-07 for PC10" in summaries

    rec = client.get(f"{API}/assessments/{aid}/record.json", headers=a07)
    assert rec.status_code == 200
    rj = rec.json()
    assert rj["title"] == "Assessment Record — not a certificate"
    assert rj["pc"]["text"].startswith("use wires strippers, crippling tool")
    assert rj["assessment"]["initial_score"] == 3 and rj["assessment"]["final_score"] == 3
    assert rj["ai_evidence"]["mode"] == "demo" and rj["audit_chain"]["ok"] is True
    assert "DigiLocker" in rj["handoff"]
    pdf = client.get(f"{API}/assessments/{aid}/record.pdf", headers=a07)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["content-type"] == "application/pdf"
    exported = client.get(f"{API}/audit?action=record.exported", headers=admin).json()
    assert len(exported) == 2

    # A-12: blind second assessment
    r = client.post(f"{API}/assessments", json={"evidence_id": ev_id, "pc_id": pc10}, headers=a12)
    assert r.status_code == 201
    b = r.json()
    bid = b["id"]
    assert b["is_second_assessor"] is True and b["blind"] is True
    assert b["initial_score"] is None and b["final_score"] is None
    payload = json.dumps(b)
    assert "Clean strip and crimp." not in payload and '"A-07"' not in payload.replace('"decided_by": "A-07"', "")
    assert client.get(f"{API}/assessments/{aid}", headers=a12).status_code == 403
    assert client.get(f"{API}/assessments/{aid}/record.json", headers=a12).status_code == 403
    mine = client.get(f"{API}/assessments", headers=a12).json()
    assert [x["id"] for x in mine] == [bid]
    m_a12 = client.get(f"{API}/evidence/{ev_id}/mappings", headers=a12).json()[0]
    assert m_a12["locked"] is True and m_a12["confidence"] is None
    assert client.post(f"{API}/assessments/{bid}/initial", json={"score": 3}, headers=a12).status_code == 200
    assert client.get(f"{API}/assessments/{bid}/ai-support", headers=a12).status_code == 200
    r = client.post(f"{API}/assessments/{bid}/final", json={"score": 3}, headers=a12)
    assert r.status_code == 200 and r.json()["final_score"] == 3

    ag = client.get(f"{API}/agreement", headers=admin).json()
    assert ag["n_pairs"] == 1 and ag["threshold"] == 30 and ag["status"] == "insufficient"
    assert ag["kappa"] is None and ag["kappa_linear"] is None and ag["exact_agreement"] is None
    assert ag["message"] == "Pilot measurement underway — 1 of 30 double-scored decisions collected."
    assert ag["data_source"] == "demo"
    assert ag["pairs"][0] == {"evidence_label": "Evidence #17", "pc_code": "PC10", "candidate": "Raj Kumar",
                              "assessor_a": "A-07", "score_a": 3, "assessor_b": "A-12", "score_b": 3, "is_demo": True}

    imp = client.get(f"{API}/analytics/impact", headers=admin).json()
    metrics = {m["key"]: m for m in imp["metrics"]}
    assert set(metrics) == {"evidence_linked_pct", "weighted_kappa", "minutes_per_candidate", "offline_sync_success"}
    for m in metrics.values():
        assert m["pilot"]["value"] is None and m["pilot"]["status"] == "insufficient", m
    assert metrics["evidence_linked_pct"]["demo"] == {"value": 100.0, "n": 2}
    assert metrics["weighted_kappa"]["demo"] == {"value": None, "n": 1}
    assert metrics["weighted_kappa"]["pilot"]["min_n"] == 30
    assert metrics["offline_sync_success"]["demo"] == {"value": 100.0, "n": 1}
    assert imp["ai_influence"]["post_reveal_change_rate"] == 0.0 and imp["ai_influence"]["n"] == 2
    assert imp["counts"]["double_scored"] == 1 and imp["counts"]["assessments"] == 2


def test_mapping_edit_and_reject(client, fresh):
    admin = fresh["admin"]
    r = client.post(f"{API}/demo/reset", json={"stage": "processed"}, headers=admin)
    assert r.status_code == 200, r.text
    a07 = login(client, "a07@kp.demo")
    ev_id = r.json()["evidence_id"]
    pc10 = _pc10_id(client, a07)
    m = client.get(f"{API}/evidence/{ev_id}/mappings", headers=a07).json()[0]
    aid = client.post(f"{API}/assessments", json={"evidence_id": ev_id, "pc_id": pc10}, headers=a07).json()["id"]
    assert client.post(f"{API}/mappings/{m['id']}/edit", json={"start_s": 40, "end_s": 70}, headers=a07).status_code == 409
    client.post(f"{API}/assessments/{aid}/initial", json={"score": 2}, headers=a07)
    r = client.post(f"{API}/mappings/{m['id']}/edit", json={"start_s": 40, "end_s": 70, "reason": "Starts earlier"},
                    headers=a07)
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["status"] == "edited" and e["statement"] == "Potential evidence supporting PC10 found at 00:40–01:10."
    log = client.get(f"{API}/audit?action=mapping.edited", headers=admin).json()[0]
    assert log["details"]["original"]["start_s"] == 42 and log["details"]["new"]["start_s"] == 40
    r = client.post(f"{API}/mappings/{m['id']}/edit", json={"start_s": 70, "end_s": 40}, headers=a07)
    assert r.status_code == 422
    r = client.post(f"{API}/mappings/{m['id']}/reject", json={"reason": "Not the right task"}, headers=a07)
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    r = client.post(f"{API}/assessments/{aid}/final", json={"score": 3, "rationale": "Reviewed full recording."},
                    headers=a07)
    assert r.status_code == 200 and r.json()["score_changed"] is True


@pytest.mark.parametrize("stage,n_assess,n_final", [
    ("fresh", 0, 0), ("processed", 0, 0), ("assessor_a_scored", 1, 1), ("both_scored", 2, 2)])
def test_demo_reset_stages(client, stage, n_assess, n_final):
    admin = login(client, "admin@kp.demo")
    r = client.post(f"{API}/demo/reset", json={"stage": stage}, headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stage"] == stage and body["audit_chain"]["ok"] is True
    admin = login(client, "admin@kp.demo")
    raj = login(client, "raj@kp.demo")
    evs = client.get(f"{API}/evidence", headers=raj).json()
    if stage == "fresh":
        assert evs == []
        nums = client.post(f"{API}/sync/reserve", json={"count": 1}, headers=raj).json()["numbers"]
        assert nums == [17]
    else:
        assert len(evs) == 1
        e = evs[0]
        assert e["label"] == "Evidence #17" and e["status"] == "ready" and e["is_demo"]
        assert e["offline_captured"] and e["encrypted_at_rest"] and e["metadata"]["sync_attempts"] == 2
        assert e["metadata"]["latitude"] == 30.3165 and e["metadata"]["longitude"] == 78.0322
        p = client.get(f"{API}/evidence/{e['id']}/processing", headers=raj).json()
        assert p["status"] == "done"
    assessments = client.get(f"{API}/assessments", headers=admin).json()
    assert len(assessments) == n_assess
    assert sum(a["status"] == "finalized" for a in assessments) == n_final
    if stage == "both_scored":
        ag = client.get(f"{API}/agreement", headers=admin).json()
        assert ag["n_pairs"] == 1 and ag["kappa"] is None and ag["status"] == "insufficient"
        a07 = next(a for a in assessments if a["assessor"]["assessor_code"] == "A-07")
        assert a07["mapping"]["status"] == "confirmed" and a07["initial_score"] == 3 and a07["final_score"] == 3
        summaries = [x["summary"] for x in client.get(f"{API}/audit?limit=500", headers=admin).json()]
        assert any(s.startswith("Demo reset to stage 'both_scored'") for s in summaries)
        assert "AI evidence revealed to A-12 for PC10" in summaries
    assert client.get(f"{API}/audit/verify", headers=admin).json()["ok"] is True


def test_admin_management(client, fresh):
    admin = fresh["admin"]
    r = client.post(f"{API}/admin/users", json={"email": "a20@kp.demo", "password": "Assessor@2026",
                                                "full_name": "Assessor C", "role": "assessor", "assessor_code": "A-20"},
                    headers=admin)
    assert r.status_code == 201 and r.json()["assessor"]["assessor_code"] == "A-20"
    uid = r.json()["id"]
    assert client.patch(f"{API}/admin/users/{uid}", json={"is_active": False}, headers=admin).json()["is_active"] is False
    r = client.post(f"{API}/auth/login", json={"email": "a20@kp.demo", "password": "Assessor@2026"})
    assert r.status_code == 403
    assert len(client.get(f"{API}/admin/users?role=assessor", headers=admin).json()) == 3
    ag = client.get(f"{API}/admin/agencies", headers=admin).json()
    assert ag[0]["code"] == "AA-DEMO" and ag[0]["assessor_count"] == 3

    q = client.get(f"{API}/qualifications", headers=admin).json()[0]
    assert q["nos_count"] == 6 and q["pc_count"] == 1
    n = client.post(f"{API}/qualifications/{q['id']}/nos", json={"code": "ISC/N9999", "title": "Test NOS"},
                    headers=admin).json()
    pc = client.post(f"{API}/nos/{n['id']}/pcs", json={"code": "PC1", "text": "Test PC text"}, headers=admin).json()
    assert pc["max_marks"] == 4 and pc["rubric"] is None
    bad = client.put(f"{API}/pcs/{pc['id']}/rubric", json={"levels": [{"score": 0, "descriptor": "x"}]}, headers=admin)
    assert bad.status_code == 422
    levels = [{"score": i, "descriptor": f"Level {i}"} for i in range(5)]
    r1 = client.put(f"{API}/pcs/{pc['id']}/rubric", json={"levels": levels, "status": "draft"}, headers=admin).json()
    r2 = client.put(f"{API}/pcs/{pc['id']}/rubric", json={"levels": levels, "status": "validated"}, headers=admin).json()
    assert (r1["version"], r2["version"], r2["status"]) == (1, 2, "validated")
    tree = client.get(f"{API}/qualifications/{q['id']}/tree", headers=admin).json()
    new_pc = next(p for nn in tree["nos"] for p in nn["pcs"] if p["id"] == pc["id"])
    assert new_pc["rubric"]["version"] == 2
