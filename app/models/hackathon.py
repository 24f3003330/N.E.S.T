"""Hackathon model — enhanced with team sizes, capabilities, tags, status."""

import enum
import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HackathonStatus(str, enum.Enum):
    UPCOMING = "Upcoming"
    ACTIVE = "Active"
    COMPLETED = "Completed"


class Hackathon(Base):
    __tablename__ = "hackathons"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    organizer: Mapped[Optional[str]] = mapped_column(String(300))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # ── Dates ──
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    registration_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    # ── Team constraints ──
    max_team_size: Mapped[Optional[int]] = mapped_column(Integer, default=5)
    min_team_size: Mapped[Optional[int]] = mapped_column(Integer, default=1)

    # ── JSON lists (stored as Text for SQLite compat) ──
    required_capabilities_json: Mapped[Optional[str]] = mapped_column(
        Text, default="[]"
    )
    tags_json: Mapped[Optional[str]] = mapped_column(Text, default="[]")

    # ── Status ──
    status: Mapped[HackathonStatus] = mapped_column(
        Enum(HackathonStatus), default=HackathonStatus.UPCOMING
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── JSON helpers ──
    @property
    def required_capabilities(self) -> List[str]:
        try:
            return json.loads(self.required_capabilities_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def tags(self) -> List[str]:
        try:
            return json.loads(self.tags_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []
