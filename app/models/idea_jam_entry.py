"""IdeaJamEntry model — individual ideas within a jam session."""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IdeaJamEntry(Base):
    __tablename__ = "idea_jam_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    jam_id: Mapped[int] = mapped_column(ForeignKey("idea_jams.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    idea_text: Mapped[str] = mapped_column(String(280), nullable=False)
    votes: Mapped[int] = mapped_column(Integer, default=0)
