"""Hash chain: concurrent writers never fork it; modification and deletion are both detected."""
from __future__ import annotations

import threading

from sqlalchemy import func, select, text

from backend.app.db import SessionLocal, get_engine
from backend.app.models import AuditLog
from backend.app.services import audit


def test_concurrent_writes_keep_a_single_chain(client, fresh):
    db = SessionLocal()
    before = db.scalar(select(func.count(AuditLog.id)))
    db.close()
    errors: list[Exception] = []

    def writer(n: int):
        s = SessionLocal()
        try:
            for i in range(15):
                audit.log(s, actor=None, action="test.concurrent", entity_type="test", entity_id=n,
                          summary=f"writer {n} entry {i}", details={"n": n, "i": i})
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            s.close()

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    db = SessionLocal()
    try:
        v = audit.verify(db)
        assert v["ok"] is True and v["entries"] == before + 8 * 15
        prevs = db.scalars(select(AuditLog.prev_hash)).all()
        assert len(prevs) == len(set(prevs))  # no two entries share a parent => no fork
    finally:
        db.close()


def test_deleted_entry_is_detected(client, fresh):
    db = SessionLocal()
    try:
        for i in range(3):
            audit.log(db, actor=None, action="test.delete", entity_type="test", entity_id=i, summary=f"e{i}")
        ids = db.scalars(select(AuditLog.id).where(AuditLog.action == "test.delete").order_by(AuditLog.id)).all()
        with get_engine().begin() as conn:
            conn.execute(text("DELETE FROM audit_log WHERE id = :i"), {"i": ids[1]})
        db.expire_all()
        v = audit.verify(db)
        assert v["ok"] is False and v["broken_at"] == ids[2] and "removed" in v["reason"]
    finally:
        db.close()
