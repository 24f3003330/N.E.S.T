"""Post-Idea Jam Survey model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JamSurvey(Base):
    __tablename__ = "jam_surveys"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    jam_id: Mapped[int] = mapped_column(ForeignKey("idea_jams.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    continue_in_team: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    avoid_member_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
