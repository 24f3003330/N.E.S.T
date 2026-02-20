"""Matching router – AI-ranked team match scores (skill + vibe)."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.team import Team
from app.models.hackathon import Hackathon
from app.models.team_membership import TeamMembership, Role
from app.routers.auth import get_current_user
from app.services.matching import score_user_for_team

router = APIRouter(prefix="/match", tags=["matching"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def match_dashboard(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Render the Match Dashboard with entry points for both Leaders and Members."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        
    # Fetch active hackathons for Members to join
    res_h = await db.execute(select(Hackathon).order_by(Hackathon.created_at.desc()))
    hackathons = res_h.scalars().all()
    
    # Fetch forming teams of which current_user is the Lead
    my_teams = []
    if current_user.account_type.value == "Leader":
        res_t = await db.execute(
            select(Team).where(Team.lead_id == current_user.id)
        )
        my_teams = res_t.scalars().all()
        
    return templates.TemplateResponse(
        "match_dashboard.html",
        {
            "request": request,
            "hackathons": hackathons,
            "my_teams": my_teams,
            "current_user": current_user
        }
    )

@router.get("/suggest/{team_id}", response_class=HTMLResponse)
async def suggest_members(
    team_id: int,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return top 10 suggested users for a team (team lead only)."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    # 1. Fetch team, verify user is lead
    res = await db.execute(select(Team).where(Team.id == team_id))
    team = res.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
        
    if team.lead_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the team lead can view suggestions")
        
    # 2. Fetch hackathon
    hackathon = None
    if team.hackathon_id:
        res_h = await db.execute(select(Hackathon).where(Hackathon.id == team.hackathon_id))
        hackathon = res_h.scalar_one_or_none()
        
    # 3. Fetch existing team members
    res_mems = await db.execute(
        select(User)
        .join(TeamMembership, TeamMembership.user_id == User.id)
        .where(TeamMembership.team_id == team_id)
        .options(selectinload(User.capabilities))
    )
    existing_members = res_mems.scalars().all()
    existing_member_ids = {m.id for m in existing_members}
    
    # 4. Fetch all other users
    res_users = await db.execute(
        select(User).options(selectinload(User.capabilities))
    )
    all_users = res_users.scalars().all()
    candidate_users = [u for u in all_users if u.id not in existing_member_ids]
    
    # 5. Score candidates
    scored_candidates = []
    for u in candidate_users:
        score_data = score_user_for_team(u, team, hackathon, existing_members)
        scored_candidates.append({
            "user": u,
            "score_data": score_data
        })
        
    # Sort by overall score descending
    scored_candidates.sort(key=lambda x: x["score_data"]["score"], reverse=True)
    
    # Return top 10
    top_10 = scored_candidates[:10]
    
    return templates.TemplateResponse(
        "suggestions.html",
        {
            "request": request,
            "suggestions": top_10,
            "team": team
        }
    )

@router.get("/teams-for-me/{hackathon_id}", response_class=HTMLResponse)
async def teams_for_me(
    hackathon_id: int,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return top 5 teams that match the logged-in user's profile."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        
    # 1. Fetch current user with capabilities
    res_u = await db.execute(
        select(User).where(User.id == current_user.id).options(selectinload(User.capabilities))
    )
    user_loaded = res_u.scalar_one_or_none()
    
    # 2. Fetch hackathon
    res_h = await db.execute(select(Hackathon).where(Hackathon.id == hackathon_id))
    hackathon = res_h.scalar_one_or_none()
    if not hackathon:
         raise HTTPException(status_code=404, detail="Hackathon not found")

    # 3. Fetch all teams serving it
    res_teams = await db.execute(select(Team).where(Team.hackathon_id == hackathon_id))
    teams = res_teams.scalars().all()
    
    # Exclude teams where user is already a member
    res_user_teams = await db.execute(
        select(TeamMembership.team_id).where(TeamMembership.user_id == current_user.id)
    )
    user_team_ids = {row[0] for row in res_user_teams.all()}
    
    candidate_teams = [t for t in teams if t.id not in user_team_ids]
    
    # Score user for each team
    scored_teams = []
    for team in candidate_teams:
        # fetch existing members for this team
        res_mems = await db.execute(
            select(User)
            .join(TeamMembership, TeamMembership.user_id == User.id)
            .where(TeamMembership.team_id == team.id)
            .options(selectinload(User.capabilities))
        )
        existing_members = res_mems.scalars().all()
        
        score_data = score_user_for_team(user_loaded, team, hackathon, existing_members)
        scored_teams.append({
            "team": team,
            "score_data": score_data,
            "member_count": len(existing_members)
        })
        
    scored_teams.sort(key=lambda x: x["score_data"]["score"], reverse=True)
    top_5 = scored_teams[:5]
    
    return templates.TemplateResponse(
        "teams_for_me.html",
        {
            "request": request,
            "suggested_teams": top_5,
            "hackathon": hackathon
        }
    )
