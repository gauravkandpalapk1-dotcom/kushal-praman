"""Login brute-force throttle and HTTP security headers."""
from backend.app.security import login_throttle


def test_login_is_throttled_after_repeated_failures(client, fresh):
    bad = {"email": "a07@kp.demo", "password": "wrong-password"}
    for _ in range(login_throttle.MAX_FAILURES):
        assert client.post("/api/v1/auth/login", json=bad).status_code == 401
    r = client.post("/api/v1/auth/login", json=bad)
    assert r.status_code == 429
    assert r.json()["code"] == "too_many_attempts"
    # Even the right password is refused while throttled.
    ok = {"email": "a07@kp.demo", "password": "Assessor@2026"}
    assert client.post("/api/v1/auth/login", json=ok).status_code == 429


def test_success_clears_failures(client, fresh):
    bad = {"email": "raj@kp.demo", "password": "nope-nope"}
    for _ in range(login_throttle.MAX_FAILURES - 1):
        client.post("/api/v1/auth/login", json=bad)
    assert client.post("/api/v1/auth/login", json={"email": "raj@kp.demo", "password": "Candidate@2026"}).status_code == 200
    assert login_throttle.retry_after("raj@kp.demo", "testclient") == 0


def test_window_expires():
    login_throttle.reset()
    for i in range(login_throttle.MAX_FAILURES):
        login_throttle.record_failure("x@y.z", "1.1.1.1", now=1000.0 + i)
    assert login_throttle.retry_after("x@y.z", "1.1.1.1", now=1010.0) > 0
    assert login_throttle.retry_after("x@y.z", "1.1.1.1", now=1000.0 + login_throttle.WINDOW_S + 10) == 0


def test_security_headers_on_api_and_ui(client):
    r = client.get("/api/v1/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    docs = client.get("/api/docs")
    assert "Content-Security-Policy" not in docs.headers  # Swagger assets come from a CDN
