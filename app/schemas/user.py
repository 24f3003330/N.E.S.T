"""User Pydantic schemas — registration, login, profile output."""

from typing import List, Optional

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    """Fields submitted on the registration form."""
    full_name: str
    email: EmailStr
    campus_id: str
    department: Optional[str] = None
    password: str


class UserLogin(BaseModel):
    """Fields submitted on the login form."""
    email: EmailStr
    password: str


class UserOut(BaseModel):
    """Public user representation returned by the API."""
    id: int
    email: str
    full_name: str
    campus_id: str
    department: Optional[str] = None
    year_of_study: Optional[int] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_username: Optional[str] = None
    archetype: Optional[str] = None

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
