"""Database engine, session factory and declarative Base.

SQLite is the default (file under database/). PostgreSQL works by setting DATABASE_URL.
The engine is created lazily so tests can point DATABASE_URL at a temp file first.
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import ROOT, get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_lock = threading.Lock()


def _make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        db_path = url.split("sqlite:///", 1)[-1]
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30}, future=True)

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()

        return engine
    return create_engine(url, pool_pre_ping=True, future=True)


def get_engine() -> Engine:
    global _engine, _session_factory
    with _lock:
        if _engine is None:
            _engine = _make_engine(get_settings().DATABASE_URL)
            _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
        return _engine


def reset_engine() -> None:
    """Dispose the engine (tests / settings changes)."""
    global _engine, _session_factory
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _session_factory = None


def SessionLocal() -> Session:  # noqa: N802 - conventional name
    get_engine()
    assert _session_factory is not None
    return _session_factory()


def get_session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def engine_name() -> str:
    return get_engine().dialect.name


def run_migrations() -> None:
    """Apply Alembic migrations up to head (idempotent)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
