"""
Hackathons & Projects router — dashboard, CRUD, filters.

Endpoints:
    GET  /hackathons/dashboard       → combined Hackathons + Projects view
    GET  /hackathons/                → list hackathons (filter by status, tag)
    GET  /hackathons/create          → create hackathon form
    POST /hackathons/create          → handle hackathon creation
    GET  /hackathons/{id}            → hackathon detail
    GET  /hackathons/projects/create → create project form
    POST /hackathons/projects/create → handle project creation
"""

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.hackathon import Hackathon, HackathonStatus
from app.models.project import Project, ProjectStatus
from app.models.team import Team
from app.models.team_membership import TeamMembership, Role
from app.models.chat_room import ChatRoom
from app.models.user import User
from app.routers.auth import get_current_user
from app.utils.unstop_feed import get_unstop_events

router = APIRouter(prefix="/hackathons", tags=["hackathons"])
templates = Jinja2Templates(directory="app/templates")


# ═══════════════════════════════════════════════════════════════
#  Dashboard — combined Hackathons + Projects
# ═══════════════════════════════════════════════════════════════

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    status_filter: Optional[str] = None,
    cap_filter: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Render the combined Hackathons + Projects dashboard."""

    # ── Hackathons ──
    hack_q = select(Hackathon).order_by(Hackathon.created_at.desc())
    if status_filter and status_filter in [s.value for s in HackathonStatus]:
        hack_q = hack_q.where(Hackathon.status == HackathonStatus(status_filter))
    result = await db.execute(hack_q)
    hackathons = result.scalars().all()

    # Capability filter (search in JSON text)
    if cap_filter:
        hackathons = [
            h for h in hackathons if cap_filter.lower() in (h.required_capabilities_json or "").lower()
        ]

    # ── Count teams per hackathon ──
    from app.models.team_membership import TeamMembership
    
    hack_team_counts = {}
    for h in hackathons:
        team_result = await db.execute(select(Team).where(Team.hackathon_id == h.id))
        teams = team_result.scalars().all()
        
        member_count = 0
        if teams:
            team_ids = [t.id for t in teams]
            mem_result = await db.execute(
                select(TeamMembership).where(TeamMembership.team_id.in_(team_ids))
            )
            memberships = mem_result.scalars().all()
            member_count = len(memberships)
            
        hack_team_counts[h.id] = {
            "teams": len(teams),
            "members": member_count,
        }

    # ── Projects ──
    proj_q = select(Project).order_by(Project.created_at.desc())
    if status_filter and status_filter in [s.value for s in ProjectStatus]:
        proj_q = proj_q.where(Project.status == ProjectStatus(status_filter))
    result = await db.execute(proj_q)
    projects = result.scalars().all()

    if cap_filter:
        projects = [
            p for p in projects if cap_filter.lower() in (p.required_capabilities_json or "").lower()
        ]

    # ── Check which hackathons current user already has a team for ──
    user_hackathon_teams = set()
    if current_user:
        user_mems = await db.execute(
            select(TeamMembership.team_id).where(TeamMembership.user_id == current_user.id)
        )
        user_team_ids = [row[0] for row in user_mems.all()]
        
        if user_team_ids:
            user_teams_result = await db.execute(
                select(Team.hackathon_id).where(Team.id.in_(user_team_ids), Team.hackathon_id.isnot(None))
            )
            user_hackathon_teams = {row[0] for row in user_teams_result.all()}

    # ── Unstop Events feed ──
    unstop_events = await get_unstop_events(query=cap_filter or status_filter or "")

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "current_user": current_user,
            "hackathons": hackathons,
            "projects": projects,
            "unstop_events": unstop_events,
            "hack_team_counts": hack_team_counts,
            "user_hackathon_teams": user_hackathon_teams,
            "statuses": [s.value for s in HackathonStatus],
            "project_statuses": [s.value for s in ProjectStatus],
            "status_filter": status_filter or "",
            "cap_filter": cap_filter or "",
        },
    )


# ═══════════════════════════════════════════════════════════════
#  List Hackathons
# ═══════════════════════════════════════════════════════════════

@router.get("/", response_class=HTMLResponse)
async def list_hackathons(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Redirect to dashboard."""
    return RedirectResponse(url="/hackathons/dashboard?success=Hackathon+created+successfully", status_code=status.HTTP_303_SEE_OTHER)


# ═══════════════════════════════════════════════════════════════
#  Create Hackathon
# ═══════════════════════════════════════════════════════════════

from app.models.user import AccountTypeEnum

@router.get("/create", response_class=HTMLResponse)
async def create_hackathon_form(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    if current_user.account_type != AccountTypeEnum.LEADER:
        raise HTTPException(status_code=403, detail="Only Leaders can create hackathons.")
    return templates.TemplateResponse(
        "hackathon_create.html",
        {
            "request": request,
            "current_user": current_user,
            "statuses": [s.value for s in HackathonStatus],
            "errors": [],
        },
    )


@router.post("/create", response_class=HTMLResponse)
async def create_hackathon(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    if current_user.account_type != AccountTypeEnum.LEADER:
        raise HTTPException(status_code=403, detail="Only Leaders can create hackathons.")

    form = await request.form()
    title = form.get("title", "").strip()
    description = form.get("description", "").strip() or None
    organizer = form.get("organizer", "").strip() or None
    min_team = int(form.get("min_team_size") or 1)
    max_team = int(form.get("max_team_size") or 5)
    start_date = form.get("start_date", "").strip() or None
    end_date = form.get("end_date", "").strip() or None
    reg_deadline = form.get("registration_deadline", "").strip() or None
    caps_raw = form.get("required_capabilities", "").strip()
    tags_raw = form.get("tags", "").strip()

    errors: list = []
    if not title:
        errors.append("Title is required.")
    if errors:
        return templates.TemplateResponse(
            "hackathon_create.html",
            {"request": request, "current_user": current_user, "errors": errors,
             "statuses": [s.value for s in HackathonStatus]},
        )

    # Parse comma-separated lists to JSON
    caps_list = [c.strip() for c in caps_raw.split(",") if c.strip()] if caps_raw else []
    tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    from datetime import datetime
    def _parse_dt(val):
        if not val:
            return None
        try:
            return datetime.fromisoformat(val)
        except ValueError:
            return None

    hackathon = Hackathon(
        title=title,
        description=description,
        organizer=organizer,
        created_by=current_user.id,
        start_date=_parse_dt(start_date),
        end_date=_parse_dt(end_date),
        registration_deadline=_parse_dt(reg_deadline),
        min_team_size=min_team,
        max_team_size=max_team,
        required_capabilities_json=json.dumps(caps_list),
        tags_json=json.dumps(tags_list),
    )
    db.add(hackathon)
    await db.commit()

    return RedirectResponse(
        url="/hackathons/dashboard?success=Hackathon+created",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ═══════════════════════════════════════════════════════════════
#  Hackathon Detail
# ═══════════════════════════════════════════════════════════════

@router.get("/{hackathon_id}", response_class=HTMLResponse)
async def hackathon_detail(
    hackathon_id: int,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Hackathon).where(Hackathon.id == hackathon_id))
    hackathon = result.scalar_one_or_none()
    if not hackathon:
        raise HTTPException(status_code=404, detail="Hackathon not found")

    # Get teams for this hackathon
    team_result = await db.execute(select(Team).where(Team.hackathon_id == hackathon_id))
    teams = team_result.scalars().all()

    return templates.TemplateResponse(
        "hackathon_detail.html",
        {
            "request": request,
            "current_user": current_user,
            "hackathon": hackathon,
            "teams": teams,
        },
    )


# ═══════════════════════════════════════════════════════════════
#  Create Project
# ═══════════════════════════════════════════════════════════════

@router.get("/projects/create", response_class=HTMLResponse)
async def create_project_form(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    if current_user.account_type != AccountTypeEnum.LEADER:
        raise HTTPException(status_code=403, detail="Only Leaders can create projects.")
    return templates.TemplateResponse(
        "project_create.html",
        {
            "request": request,
            "current_user": current_user,
            "statuses": [s.value for s in ProjectStatus],
            "errors": [],
        },
    )


@router.post("/projects/create", response_class=HTMLResponse)
async def create_project(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    if current_user.account_type != AccountTypeEnum.LEADER:
        raise HTTPException(status_code=403, detail="Only Leaders can create projects.")

    form = await request.form()
    title = form.get("title", "").strip()
    description = form.get("description", "").strip() or None
    domain = form.get("domain", "").strip() or None
    github_url = form.get("github_repo_url", "").strip() or None
    caps_raw = form.get("required_capabilities", "").strip()

    if not title:
        return templates.TemplateResponse(
            "project_create.html",
            {"request": request, "current_user": current_user,
             "errors": ["Title is required."],
             "statuses": [s.value for s in ProjectStatus]},
        )

    caps_list = [c.strip() for c in caps_raw.split(",") if c.strip()] if caps_raw else []

    project = Project(
        title=title,
        description=description,
        domain=domain,
        created_by=current_user.id,
        github_repo_url=github_url,
        required_capabilities_json=json.dumps(caps_list),
    )
    db.add(project)
    await db.commit()

    return RedirectResponse(
        url="/hackathons/dashboard?success=Project+created",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ═══════════════════════════════════════════════════════════════
#  Unstop "Participate" Flow (Turn external event into Project)
# ═══════════════════════════════════════════════════════════════

@router.post("/unstop/participate")
async def post_unstop_participate(
    request: Request,
    title: str = Form(...),
    url: str = Form(...),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    User clicks 'Participate' on an Unstop event.
    Converts it into a N.E.S.T Project and promotes them to Lead.
    """
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    # Automatically promote to Leader if they aren't one, so they can lead this competition
    if current_user.account_type != AccountTypeEnum.LEADER:
        current_user.account_type = AccountTypeEnum.LEADER
        await db.commit()

    # Create the Project locally linking to the external event
    description = f"Collaboration space for the Unstop competition: <a href='{url}' target='_blank'>{url}</a>"
    
    project = Project(
        title=f"[Unstop] {title}",
        description=description,
        domain="Competition",
        created_by=current_user.id,
        status=ProjectStatus.IDEATION,
    )
    db.add(project)
    await db.flush()  # To get project.id

    # Add the user as Lead of the project
    # Projects don't have memberships directly in this schema usually, but we convert this into a Team immediately
    # Since they clicked participate, they are forming a team for it.
    
    team = Team(
        name=f"Team for {title[:40]}",
        description=description,
        lead_id=current_user.id,
        project_id=project.id,
        max_size=5,  # Default
    )
    db.add(team)
    await db.flush()

    # Add membersip
    membership = TeamMembership(
        team_id=team.id,
        user_id=current_user.id,
        role=Role.Lead,
    )
    db.add(membership)

    # Create coordination chat room
    chat_room = ChatRoom(team_id=team.id)
    db.add(chat_room)

    await db.commit()

    return RedirectResponse(url=f"/teams/{team.id}?success=Project+created+and+team+formed", status_code=status.HTTP_303_SEE_OTHER)
