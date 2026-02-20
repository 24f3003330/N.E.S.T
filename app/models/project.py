"""Project model — non-hackathon, ongoing projects."""

import enum
import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProjectStatus(str, enum.Enum):
    IDEATION = "Ideation"
    ACTIVE = "Active"
    COMPLETED = "Completed"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    domain: Mapped[Optional[str]] = mapped_column(String(200))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # ── JSON list (stored as Text for SQLite compat) ──
    required_capabilities_json: Mapped[Optional[str]] = mapped_column(
        Text, default="[]"
    )

    # ── Status ──
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.IDEATION
    )

    github_repo_url: Mapped[Optional[str]] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── JSON helper ──
    @property
    def required_capabilities(self) -> List[str]:
        try:
            return json.loads(self.required_capabilities_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []
