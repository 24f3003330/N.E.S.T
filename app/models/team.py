"""Team model."""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TeamStatus(str, enum.Enum):
    Forming = "Forming"
    Active = "Active"
    Completed = "Completed"


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    lead_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    hackathon_id: Mapped[Optional[int]] = mapped_column(ForeignKey("hackathons.id"))
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"))
    
    status: Mapped[TeamStatus] = mapped_column(Enum(TeamStatus), default=TeamStatus.Forming)
    max_size: Mapped[Optional[int]] = mapped_column(Integer)
    
    github_repo_url: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
