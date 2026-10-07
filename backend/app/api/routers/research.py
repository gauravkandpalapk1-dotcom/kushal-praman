from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from backend.app.api.deps import DB
from backend.app.models import ResearchReference
from backend.app.schemas.misc import ResearchOut

router = APIRouter(tags=["research"])


@router.get("/research", response_model=list[ResearchOut], summary="Research & design basis (public)")
def research(db: DB):
    return [{"number": r.number, "short": r.short, "citation": r.citation, "url": r.url, "doi": r.doi,
             "category": r.category, "what_it_says": r.what_it_says, "design_decision": r.design_decision,
             "where_in_product": list(r.where_in_product or [])}
            for r in db.scalars(select(ResearchReference).order_by(ResearchReference.number))]
