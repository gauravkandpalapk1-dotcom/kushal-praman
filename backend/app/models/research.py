"""Research references that justify design decisions."""
from __future__ import annotations

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base


class ResearchReference(Base):
    __tablename__ = "research_references"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True)
    short: Mapped[str] = mapped_column(String(200))
    citation: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[str] = mapped_column(String(40))
    what_it_says: Mapped[str] = mapped_column(Text)
    design_decision: Mapped[str] = mapped_column(Text)
    where_in_product: Mapped[list] = mapped_column(JSON, default=list)
