"""Import every model so Base.metadata is complete (Alembic autogenerate, wipes)."""
from backend.app.models.assessment import Assessment, AssessmentScore
from backend.app.models.audit import AuditLog
from backend.app.models.evidence import AIAnalysis, Evidence, EvidenceMapping, EvidenceMetadata, EvidenceSegment
from backend.app.models.qualifications import NOS, PerformanceCriterion, Qualification, Rubric, RubricLevel
from backend.app.models.research import ResearchReference
from backend.app.models.sync import SyncQueue
from backend.app.models.users import AssessmentAgency, Assessor, Candidate, EvidenceNumberReservation, User

__all__ = [
    "AIAnalysis", "Assessment", "AssessmentAgency", "AssessmentScore", "Assessor", "AuditLog", "Candidate",
    "Evidence", "EvidenceMapping", "EvidenceMetadata", "EvidenceNumberReservation", "EvidenceSegment", "NOS",
    "PerformanceCriterion", "Qualification", "ResearchReference", "Rubric", "RubricLevel", "SyncQueue", "User",
]
