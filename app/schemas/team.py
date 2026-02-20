"""Team Pydantic schemas."""

from typing import List, Optional

from pydantic import BaseModel


class TeamCreate(BaseModel):
    name: str
    description: Optional[str] = None
    hackathon_id: Optional[int] = None


class TeamOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    lead_id: int
    hackathon_id: Optional[int] = None
    member_ids_json: Optional[str] = None
    github_repo_url: Optional[str] = None

    model_config = {"from_attributes": True}


class JoinRequestCreate(BaseModel):
    team_id: int
    message: Optional[str] = None


class JoinRequestOut(BaseModel):
    id: int
    team_id: int
    user_id: int
    message: Optional[str] = None
    status: str

    model_config = {"from_attributes": True}
