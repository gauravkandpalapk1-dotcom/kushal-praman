"""User accounts: registration, login, admin management."""
from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.errors import BadRequest, Conflict, Forbidden, NotFound, Unauthorized, Unprocessable
from backend.app.models import AssessmentAgency, Assessor, Candidate, Qualification, User
from backend.app.security.passwords import hash_password, verify_password
from backend.app.services import audit
from backend.app.timeutil import utcnow


def _next_code(db: Session, model, column, prefix: str, width: int) -> str:
    codes = db.scalars(select(column)).all()
    nums = [int(m.group(1)) for c in codes if (m := re.fullmatch(rf"{re.escape(prefix)}(\d+)", c or ""))]
    return f"{prefix}{(max(nums) + 1 if nums else 1):0{width}d}"


def _default_agency(db: Session) -> AssessmentAgency | None:
    return db.scalar(select(AssessmentAgency).order_by(AssessmentAgency.id).limit(1))


def create_user(db: Session, *, actor: User | None, email: str, password: str, full_name: str, role: str,
                assessor_code: str | None = None, qualification_id: int | None = None,
                preferred_language: str | None = None, district: str | None = None,
                action: str = "auth.register") -> User:
    email = email.strip().lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)) is not None:
        raise Conflict("An account with this email already exists.", "email_taken")
    if qualification_id is not None and db.get(Qualification, qualification_id) is None:
        raise Unprocessable("Unknown qualification_id.", "unknown_qualification")
    try:
        with audit.write_lock():
            u = User(email=email, password_hash=hash_password(password), full_name=full_name.strip(), role=role)
            db.add(u)
            db.flush()
            extra = ""
            if role == "candidate":
                qid = qualification_id or db.scalar(select(Qualification.id).order_by(Qualification.id).limit(1))
                code = _next_code(db, Candidate, Candidate.candidate_code, "CAND-", 4)
                db.add(Candidate(user_id=u.id, candidate_code=code, qualification_id=qid,
                                 preferred_language=preferred_language, district=district, next_evidence_number=1))
                extra = f" ({code})"
            elif role == "assessor":
                if assessor_code:
                    if db.scalar(select(Assessor.id).where(Assessor.assessor_code == assessor_code)) is not None:
                        raise Conflict("Assessor code already in use.", "assessor_code_taken")
                    code = assessor_code
                else:
                    code = _next_code(db, Assessor, Assessor.assessor_code, "A-", 2)
                agency = _default_agency(db)
                db.add(Assessor(user_id=u.id, assessor_code=code, agency_id=agency.id if agency else None))
                extra = f" ({code})"
            db.flush()
            summary = (f"{full_name} registered as {role}{extra}" if action == "auth.register"
                       else f"Admin created {role} account for {full_name}{extra}")
            audit.log(db, actor=actor or u, action=action, entity_type="user", entity_id=u.id, summary=summary,
                      details={"email": email, "role": role})
    except IntegrityError:
        db.rollback()
        raise Conflict("An account with this email already exists.", "email_taken")
    db.refresh(u)
    return u


def register(db: Session, data) -> User:
    if data.role == "admin":
        raise Forbidden("Admin accounts cannot be self-registered.", "admin_registration_forbidden")
    return create_user(db, actor=None, email=data.email, password=data.password, full_name=data.full_name,
                       role=data.role, qualification_id=data.qualification_id,
                       preferred_language=data.preferred_language, district=data.district)


def login(db: Session, email: str, password: str) -> User:
    u = db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    if u is None or not verify_password(password, u.password_hash):
        raise Unauthorized("Incorrect email or password.", "invalid_credentials")
    if not u.is_active:
        raise Forbidden("This account is disabled.", "account_disabled")
    u.last_login_at = utcnow()
    code = u.assessor.assessor_code if u.assessor else (u.candidate.candidate_code if u.candidate else u.role)
    audit.log(db, actor=u, action="auth.login", entity_type="user", entity_id=u.id,
              summary=f"{u.full_name} ({code}) signed in", details={"role": u.role})
    return u


def set_active(db: Session, admin: User, user_id: int, is_active: bool) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise NotFound("User not found.", "user_not_found")
    if u.id == admin.id and not is_active:
        raise BadRequest("You cannot deactivate your own account.", "cannot_deactivate_self")
    u.is_active = is_active
    audit.log(db, actor=admin, action="admin.user_updated", entity_type="user", entity_id=u.id,
              summary=f"Admin {'activated' if is_active else 'deactivated'} {u.full_name}",
              details={"is_active": is_active})
    return u
