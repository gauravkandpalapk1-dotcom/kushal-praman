from __future__ import annotations

import json
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Header, Query, Response, UploadFile
from pydantic import ValidationError

from backend.app.api.deps import DB, CandidateUser, CurrentUser, StaffUser
from backend.app.errors import NotFound, Unprocessable
from backend.app.models import Evidence
from backend.app.schemas.evidence import EvidenceMetaIn, EvidenceOut, ProcessingOut, WorkspaceOut
from backend.app.schemas.mapping import MappingOut
from backend.app.security import media_tokens
from backend.app.services import evidence as svc
from backend.app.services import mapping as mapping_svc
from backend.app.services import media, pipeline, workspace
from backend.app.services import presenters as P

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.post("", response_model=EvidenceOut, status_code=201,
             responses={200: {"description": "Idempotent repeat (same local_id): existing record"},
                        413: {"description": "File too large"}, 415: {"description": "Type not allowed"}})
def upload(response: Response, db: DB, user: CandidateUser,
           file: Annotated[UploadFile, File(description="Evidence file")],
           meta: Annotated[str, Form(description="EvidenceMetaIn as a JSON string")]):
    try:
        meta_in = EvidenceMetaIn.model_validate(json.loads(meta))
    except json.JSONDecodeError as exc:
        raise Unprocessable("`meta` must be a JSON object string.", "invalid_meta") from exc
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(x) for x in first.get("loc", ()))
        raise Unprocessable(f"meta.{loc}: {first.get('msg')}", "invalid_meta") from exc
    ev, created = svc.ingest(db, user, file.file, filename=file.filename, content_type=file.content_type, meta=meta_in)
    if not created:
        response.status_code = 200
    return P.evidence_out(ev)


@router.get("", response_model=list[EvidenceOut])
def list_evidence(db: DB, user: CurrentUser,
                  status: Literal["received", "processing", "ready", "failed"] | None = None,
                  candidate_id: int | None = None):
    return [P.evidence_out(e) for e in svc.list_for_viewer(db, user, status=status, candidate_id=candidate_id)]


@router.get("/{evidence_id}", response_model=EvidenceOut)
def get_evidence(evidence_id: int, db: DB, user: CurrentUser):
    return P.evidence_out(svc.get_for_viewer(db, evidence_id, user))


@router.get("/{evidence_id}/media", summary="Stream evidence media (HMAC token, HTTP Range supported)",
            response_class=Response, responses={206: {"description": "Partial content"}})
def evidence_media(evidence_id: int, db: DB, t: Annotated[str | None, Query(description="media token")] = None,
                   range_header: Annotated[str | None, Header(alias="Range")] = None):
    media_tokens.verify(evidence_id, t)
    ev = db.get(Evidence, evidence_id)
    if ev is None:
        raise NotFound("Evidence not found.", "evidence_not_found")
    return media.file_response(svc.stored_path(ev), ev.mime_type, range_header)


@router.post("/{evidence_id}/process", response_model=ProcessingOut, status_code=202)
def process(evidence_id: int, db: DB, user: StaffUser, force: bool = False):
    ev = svc.get_for_viewer(db, evidence_id, user)
    return pipeline.start(db, ev, user, force=force)


@router.get("/{evidence_id}/processing", response_model=ProcessingOut)
def processing(evidence_id: int, db: DB, user: CurrentUser):
    return pipeline.processing_out(db, svc.get_for_viewer(db, evidence_id, user))


@router.get("/{evidence_id}/workspace", response_model=WorkspaceOut,
            summary="Tier-1 view: segments, transcript, surfaced statements (no confidence)")
def get_workspace(evidence_id: int, db: DB, user: StaffUser):
    return workspace.build(db, svc.get_for_viewer(db, evidence_id, user))


@router.get("/{evidence_id}/mappings", response_model=list[MappingOut],
            summary="Evidence→PC mappings; interpretive fields tier-gated")
def mappings(evidence_id: int, db: DB, user: CurrentUser):
    ev = svc.get_for_viewer(db, evidence_id, user)
    return mapping_svc.list_for_evidence(db, ev, user)
