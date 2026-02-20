"""Hackathon Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class HackathonCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class HackathonOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    created_by: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    model_config = {"from_attributes": True}
