"""Auth, RBAC, upload security, idempotency, media streaming, audit tamper detection."""
from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import text

from backend.app.db import get_engine
from backend.tests.conftest import DEMO_VIDEO, login

API = "/api/v1"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 64


def _meta(content: bytes, **kw) -> str:
    m = {"local_id": str(uuid.uuid4()), "kind": "photo", "qualification_id": 1,
         "client_sha256": hashlib.sha256(content).hexdigest(), "captured_at": "2026-10-07T08:00:00Z",
         "latitude": 30.3165, "longitude": 78.0322, "offline_captured": True, "sync_attempts": 1}
    m.update(kw)
    return json.dumps(m)


def _upload(client, headers, content: bytes, meta: str, name="photo.png", ctype="image/png"):
    return client.post(f"{API}/evidence", headers=headers, files={"file": (name, content, ctype)}, data={"meta": meta})


def test_register_login_me_and_admin_forbidden(client, fresh):
    r = client.post(f"{API}/auth/register", json={"email": "new.cand@kp.demo", "password": "Password@1",
                                                  "full_name": "New Candidate", "role": "candidate"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 480 * 60
    assert body["user"]["candidate"]["candidate_code"].startswith("CAND-")
    h = {"Authorization": f"Bearer {body['access_token']}"}
    me = client.get(f"{API}/auth/me", headers=h).json()
    assert me["email"] == "new.cand@kp.demo" and me["assessor"] is None

    r = client.post(f"{API}/auth/register", json={"email": "x@kp.demo", "password": "Password@1",
                                                  "full_name": "X", "role": "admin"})
    assert r.status_code == 403 and r.json()["code"] == "admin_registration_forbidden"
    r = client.post(f"{API}/auth/register", json={"email": "new.cand@kp.demo", "password": "Password@1",
                                                  "full_name": "Dup", "role": "candidate"})
    assert r.status_code == 409
    r = client.post(f"{API}/auth/register", json={"email": "short@kp.demo", "password": "x", "full_name": "S",
                                                  "role": "candidate"})
    assert r.status_code == 422 and r.json()["code"] == "validation_error"

    r = client.post(f"{API}/auth/login", json={"email": "raj@kp.demo", "password": "wrong-password"})
    assert r.status_code == 401 and r.json() == {"detail": "Incorrect email or password.", "code": "invalid_credentials"}
    me = client.get(f"{API}/auth/me", headers=fresh["a07"]).json()
    assert me["assessor"]["assessor_code"] == "A-07" and me["assessor"]["agency"]["code"] == "AA-DEMO"
    assert client.get(f"{API}/auth/me").status_code == 401
    assert client.get(f"{API}/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401

    audit = client.get(f"{API}/audit?action=auth.login", headers=fresh["admin"]).json()
    assert audit and all("password" not in json.dumps(e["details"]).lower() for e in audit)


def test_rbac_denials(client, fresh):
    assert client.get(f"{API}/audit", headers=fresh["raj"]).status_code == 403
    assert client.get(f"{API}/agreement", headers=fresh["a07"]).status_code == 403
    assert client.get(f"{API}/analytics/impact", headers=fresh["raj"]).status_code == 403
    assert client.get(f"{API}/admin/users", headers=fresh["a07"]).status_code == 403
    assert client.post(f"{API}/assessments", json={"evidence_id": 1, "pc_id": 1}, headers=fresh["raj"]).status_code == 403
    assert client.post(f"{API}/demo/reset", json={"stage": "fresh"}, headers=fresh["a07"]).status_code == 403
    assert client.post(f"{API}/qualifications", json={"title": "x", "nqr_code": "y", "nsqf_level": 3},
                       headers=fresh["a07"]).status_code == 403
    r = _upload(client, fresh["a07"], PNG, _meta(PNG))
    assert r.status_code == 403
    assert client.get(f"{API}/research").status_code == 200
    assert client.get(f"{API}/health").status_code == 200


def test_upload_hash_match_mismatch_idempotency_and_errors(client, fresh, settings):
    raj = fresh["raj"]
    meta = _meta(PNG)
    r = _upload(client, raj, PNG, meta)
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["integrity_ok"] is True and ev["display_number"] == 17 and ev["label"] == "Evidence #17"
    assert ev["sha256"] == hashlib.sha256(PNG).hexdigest() and ev["status"] == "received" and ev["is_demo"] is False
    assert ev["media_url"].startswith(f"/api/v1/evidence/{ev['id']}/media?t=")

    again = _upload(client, raj, PNG, meta)
    assert again.status_code == 200 and again.json()["id"] == ev["id"]

    bad = _upload(client, raj, PNG, _meta(PNG, client_sha256="0" * 64))
    assert bad.status_code == 201 and bad.json()["integrity_ok"] is False and bad.json()["display_number"] == 18
    actions = [e["action"] for e in client.get(f"{API}/audit?entity_type=evidence", headers=fresh["admin"]).json()]
    assert "evidence.integrity_verified" in actions and "evidence.integrity_failed" in actions

    # reserved numbers are honoured
    nums = client.post(f"{API}/sync/reserve", json={"count": 3}, headers=raj).json()["numbers"]
    assert nums == [19, 20, 21]
    png2 = PNG + b"x"
    r = _upload(client, raj, png2, _meta(png2, reserved_number=20))
    assert r.json()["display_number"] == 20

    # 415: wrong magic bytes / disallowed type
    assert _upload(client, raj, b"MZ" + b"\x00" * 40, _meta(b"MZ"), name="x.png").status_code == 415
    assert _upload(client, raj, b"<html></html>", _meta(b"<html>"), name="x.html", ctype="text/html").status_code == 415

    # 413: shrink the limit temporarily
    old = settings.MAX_UPLOAD_MB
    settings.MAX_UPLOAD_MB = 0.001  # ~1 KB
    try:
        big = PNG + b"\x00" * 4096
        r = _upload(client, raj, big, _meta(big))
        assert r.status_code == 413 and r.json()["code"] == "file_too_large"
    finally:
        settings.MAX_UPLOAD_MB = old

    # 422: bad meta
    r = client.post(f"{API}/evidence", headers=raj, files={"file": ("p.png", PNG, "image/png")}, data={"meta": "{"})
    assert r.status_code == 422

    # a candidate sees only their own evidence
    other = client.post(f"{API}/auth/register", json={"email": "c2@kp.demo", "password": "Password@1",
                                                      "full_name": "Other", "role": "candidate"}).json()
    oh = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.get(f"{API}/evidence", headers=oh).json() == []
    assert client.get(f"{API}/evidence/{ev['id']}", headers=oh).status_code == 403
    # sync stats
    stats = client.get(f"{API}/sync/stats", headers=fresh["admin"]).json()
    assert stats["synced"] >= 3 and stats["failed"] == 0


def test_media_token_and_range(client, fresh):
    content = DEMO_VIDEO.read_bytes()
    meta = _meta(content, kind="video")
    ev = _upload(client, fresh["raj"], content, meta, name="practical.mp4", ctype="video/mp4").json()
    assert ev["is_demo"] is True
    url = ev["media_url"]
    full = client.get(url)
    assert full.status_code == 200 and len(full.content) == len(content)
    assert full.headers["accept-ranges"] == "bytes"
    part = client.get(url, headers={"Range": "bytes=100-199"})
    assert part.status_code == 206 and part.content == content[100:200]
    assert part.headers["content-range"] == f"bytes 100-199/{len(content)}"
    assert client.get(url, headers={"Range": f"bytes={len(content) + 10}-"}).status_code == 416
    assert client.get(f"/api/v1/evidence/{ev['id']}/media").status_code == 403
    assert client.get(f"/api/v1/evidence/{ev['id']}/media?t=1.deadbeef").status_code == 403
    other_ev_url = url.replace(f"/evidence/{ev['id']}/", f"/evidence/{ev['id'] + 1}/")
    assert client.get(other_ev_url).status_code == 403
    demo = client.get("/api/v1/demo/media/practical", headers={"Range": "bytes=0-15"})
    assert demo.status_code == 206 and demo.content == content[:16]


def test_audit_chain_detects_tampering(client, fresh):
    admin = fresh["admin"]
    v = client.get(f"{API}/audit/verify", headers=admin).json()
    assert v["ok"] is True and v["broken_at"] is None and v["entries"] >= 1
    target = client.get(f"{API}/audit?limit=1", headers=admin).json()[0]["id"]
    with get_engine().begin() as conn:
        conn.execute(text("UPDATE audit_log SET summary = 'tampered' WHERE id = :i"), {"i": target})
    v = client.get(f"{API}/audit/verify", headers=admin).json()
    assert v["ok"] is False and v["broken_at"] == target
    health = client.get(f"{API}/health").json()
    assert health["audit_chain"]["ok"] is False and health["status"] == "degraded"
    # restore a clean state for later tests
    assert client.post(f"{API}/demo/reset", json={"stage": "fresh"}, headers=login(client, "admin@kp.demo")).status_code == 200
    assert client.get(f"{API}/audit/verify", headers=login(client, "admin@kp.demo")).json()["ok"] is True


def test_health_shape(client):
    h = client.get(f"{API}/health").json()
    assert h["mode"] == "demo" and h["db"] == {"ok": True, "engine": "sqlite"}
    assert h["ffmpeg"]["available"] is True
    keys = {s["key"] for s in h["services"]}
    assert {"segmentation", "speech", "vision", "ocr", "llm", "mapper", "guardrail"} <= keys
    for s in h["services"]:
        assert {"key", "name", "provider", "available", "mode", "detail"} <= set(s)
    ocr = next(s for s in h["services"] if s["key"] == "ocr")
    assert ocr["available"] is False and ocr["mode"] == "unavailable"


def test_frontend_fallback_and_errors(client):
    root = client.get("/")
    assert root.status_code == 200 and root.json()["docs"] == "/api/docs"
    r = client.get("/api/v1/nope")
    assert r.status_code == 404 and set(r.json()) >= {"detail", "code"}
    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/api/docs").status_code == 200
