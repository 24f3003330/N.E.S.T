"""Capability model — skills / competencies linked to users."""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CategoryEnum(str, enum.Enum):
    TECHNICAL = "Technical"
    DESIGN = "Design"
    DOMAIN = "Domain"
    SOFT_SKILL = "Soft Skill"


class ProficiencyEnum(str, enum.Enum):
    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"
    EXPERT = "Expert"


class Capability(Base):
    __tablename__ = "capabilities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[CategoryEnum] = mapped_column(
        Enum(CategoryEnum), nullable=False
    )
    proficiency_level: Mapped[ProficiencyEnum] = mapped_column(
        Enum(ProficiencyEnum), default=ProficiencyEnum.BEGINNER
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── FK to User ──
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # ── Relationship back to User ──
    user: Mapped["User"] = relationship("User", back_populates="capabilities")  # noqa: F821
