"""FastAPI application factory.

* API under /api/v1, Swagger at /api/docs, OpenAPI at /api/openapi.json
* Errors are always {"detail", "code"}; no stack traces leak
* On startup: Alembic upgrade head, idempotent seed, demo-asset hash
* If FRONTEND_DIST exists, the static UI is served at / for non-/api paths
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.api.routers import (
    admin,
    agreement,
    analytics,
    assessments,
    audit,
    auth,
    demo,
    evidence,
    mappings,
    qualifications,
    research,
    sync,
    system,
)
from backend.app.config import APP_VERSION, get_settings
from backend.app.errors import AppError

log = logging.getLogger("kp")
API_PREFIX = "/api/v1"

_STATUS_CODES = {400: "bad_request", 401: "not_authenticated", 403: "forbidden", 404: "not_found",
                 405: "method_not_allowed", 409: "conflict", 413: "file_too_large", 415: "unsupported_media_type",
                 416: "range_not_satisfiable", 422: "validation_error", 429: "too_many_requests"}


def _err(status: int, detail: str, code: str, **extra) -> JSONResponse:
    return JSONResponse({"detail": detail, "code": code, **extra}, status_code=status)


def _startup() -> None:
    from backend.app.db import SessionLocal, run_migrations
    from backend.app.services import ai_runtime, seed

    s = get_settings()
    s.uploads_dir.mkdir(parents=True, exist_ok=True)
    s.tmp_dir.mkdir(parents=True, exist_ok=True)
    run_migrations()
    db = SessionLocal()
    try:
        seed.run(db)
    finally:
        db.close()
    demo = ai_runtime.demo_provider()
    if demo.asset_available:
        log.info("demo asset sha256=%s", demo.asset_sha256)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _startup()
    yield


def _register_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_req: Request, exc: AppError):
        return _err(exc.status_code, exc.detail, exc.code)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_req: Request, exc: StarletteHTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _err(exc.status_code, detail, _STATUS_CODES.get(exc.status_code, "error"))

    @app.exception_handler(RequestValidationError)
    async def _validation(_req: Request, exc: RequestValidationError):
        errors = [{"loc": [str(x) for x in e.get("loc", ())], "msg": e.get("msg", "")} for e in exc.errors()]
        first = errors[0] if errors else {"loc": [], "msg": "Invalid request."}
        where = ".".join(x for x in first["loc"] if x not in ("body", "query", "path"))
        return _err(422, f"{where}: {first['msg']}" if where else first["msg"], "validation_error", errors=errors)

    @app.exception_handler(Exception)
    async def _unhandled(_req: Request, exc: Exception):
        log.exception("unhandled error: %s", exc)
        return _err(500, "Internal server error.", "internal_error")


def _register_upload_guard(app: FastAPI) -> None:
    @app.middleware("http")
    async def _content_length_guard(request: Request, call_next):
        if request.method == "POST" and request.url.path == f"{API_PREFIX}/evidence":
            cl = request.headers.get("content-length")
            limit = get_settings().max_upload_bytes + 1024 * 1024  # allow multipart overhead
            if cl and cl.isdigit() and int(cl) > limit:
                return _err(413, f"File exceeds the {get_settings().MAX_UPLOAD_MB:g} MB limit.", "file_too_large")
        return await call_next(request)


# The UI is a static export (inline bootstrap scripts), so script-src needs 'unsafe-inline'; everything
# else is same-origin only. Swagger/ReDoc load their assets from a CDN, so they are exempt from the CSP.
_CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; font-src 'self' data:; "
        "worker-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")


def _register_security_headers(app: FastAPI) -> None:
    @app.middleware("http")
    async def _security_headers(request: Request, call_next):
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=(self)")
        if not request.url.path.startswith(("/api/docs", "/api/redoc")):
            h.setdefault("Content-Security-Policy", _CSP)
        return response


def _segment_file(rel: str) -> str:
    """Map a Next.js segment-prefetch URL to its exported file.

    The client requests ``login/__next.login.__PAGE__.txt``; ``next build`` writes
    ``login/__next.login/__PAGE__.txt`` (dots in the segment path become directories).
    """
    head, _, name = rel.rpartition("/")
    if not (name.startswith("__next.") and name.endswith(".txt")):
        return ""
    segments = name[len("__next."):-len(".txt")].replace(".", "/")
    mapped = f"__next.{segments}.txt"
    # Only the final component keeps its extension; "__next.a/b/__PAGE__.txt"
    return f"{head}/{mapped}" if head else mapped


def _register_frontend(app: FastAPI) -> None:
    dist = Path(get_settings().FRONTEND_DIST)

    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    async def _root():
        index = dist / "index.html"
        if index.is_file():
            return FileResponse(index)
        return {"name": "Kaushal Pramaan API", "version": APP_VERSION, "docs": "/api/docs",
                "health": f"{API_PREFIX}/health", "frontend": "not built (FRONTEND_DIST missing)"}

    # HEAD is needed because Next.js link prefetching probes routes with HEAD requests.
    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def _static(full_path: str):
        if full_path.startswith("api/") or full_path == "api" or not dist.is_dir():
            return _err(404, "Not found.", "not_found")
        root = dist.resolve()
        rel = full_path.strip("/")
        for cand in (rel, f"{rel}.html", f"{rel}/index.html", _segment_file(rel)):
            if not cand:
                continue
            p = (root / cand).resolve()
            if p.is_file() and (p == root or root in p.parents):
                return FileResponse(p)
        not_found = root / "404.html"
        if not_found.is_file():
            return FileResponse(not_found, status_code=404)
        index = root / "index.html"
        if index.is_file():
            return FileResponse(index)
        return _err(404, "Not found.", "not_found")


def create_app() -> FastAPI:
    s = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = FastAPI(
        title="Kaushal Pramaan API",
        version=APP_VERSION,
        description=("Evidence-intelligence layer for Recognition of Prior Learning (SIH26242). "
                     "AI finds the evidence; the assessor decides. Interpretive AI output is server-gated until "
                     "the assessor's initial score is locked."),
        docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json", lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Range", "Accept-Ranges",
                                                                                 "Content-Disposition"])
    _register_handlers(app)
    _register_upload_guard(app)
    _register_security_headers(app)
    for r in (auth, qualifications, evidence, mappings, assessments, audit, agreement, analytics, sync, admin,
              research, system, demo):
        app.include_router(r.router, prefix=API_PREFIX)
    _register_frontend(app)
    return app


app = create_app()
