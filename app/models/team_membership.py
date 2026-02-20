"""Team Membership model."""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Role(str, enum.Enum):
    Lead = "Lead"
    Member = "Member"


class TeamMembership(Base):
    __tablename__ = "team_memberships"

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.Member)
    
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
