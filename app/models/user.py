"""User model — expanded profile for N.E.S.T."""

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ArchetypeEnum(str, enum.Enum):
    BUILDER = "Builder"
    DESIGNER = "Designer"
    RESEARCHER = "Researcher"
    COMMUNICATOR = "Communicator"
    STRATEGIST = "Strategist"


class AccountTypeEnum(str, enum.Enum):
    LEADER = "Leader"
    MEMBER = "Member"


class User(Base):
    __tablename__ = "users"

    # ── Identity ──
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    account_type: Mapped[AccountTypeEnum] = mapped_column(Enum(AccountTypeEnum), default=AccountTypeEnum.MEMBER)

    # ── OAuth ──
    oauth_provider: Mapped[Optional[str]] = mapped_column(String(20))
    oauth_id: Mapped[Optional[str]] = mapped_column(String(255))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))

    # ── Campus info ──
    campus_id: Mapped[Optional[str]] = mapped_column(
        String(50), unique=True, index=True
    )
    department: Mapped[Optional[str]] = mapped_column(String(150))
    year_of_study: Mapped[Optional[int]] = mapped_column(Integer)

    # ── Profile ──
    bio: Mapped[Optional[str]] = mapped_column(Text)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500))
    github_username: Mapped[Optional[str]] = mapped_column(String(100))
    archetype: Mapped[Optional[ArchetypeEnum]] = mapped_column(Enum(ArchetypeEnum))

    # ── Timestamps ──
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ──
    capabilities: Mapped[List["Capability"]] = relationship(  # noqa: F821
        "Capability", back_populates="user", cascade="all, delete-orphan"
    )
