"""Idea Jam router — timed 10-minute brainstorming sessions."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.idea_jam import IdeaJam, JamStatus
from app.models.idea_jam_entry import IdeaJamEntry
from app.models.jam_survey import JamSurvey
from app.models.team import Team, TeamStatus
from app.models.team_membership import TeamMembership
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/ideajam", tags=["ideajam"])
templates = Jinja2Templates(directory="app/templates")

JAM_DURATION_MINUTES = 10


async def _check_team_member(db: AsyncSession, user_id: int, team_id: int) -> bool:
    """Return True if user is an active member of the team."""
    result = await db.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == user_id,
            TeamMembership.left_at.is_(None),
        )
    )
    return result.scalar_one_or_none() is not None


# ═══════════════════════════════════════════════════════════════
#  POST /ideajam/start/{team_id} → start a 10-min session
# ═══════════════════════════════════════════════════════════════

@router.post("/start/{team_id}")
async def start_jam(
    team_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    # Check team exists
    team_result = await db.execute(select(Team).where(Team.id == team_id))
    team = team_result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Check user is a member
    if not await _check_team_member(db, current_user.id, team_id):
        raise HTTPException(status_code=403, detail="You are not a member of this team")

    # Check no active jam already exists
    active_result = await db.execute(
        select(IdeaJam).where(
            IdeaJam.team_id == team_id,
            IdeaJam.status == JamStatus.Active,
        )
    )
    existing = active_result.scalar_one_or_none()
    if existing:
        return RedirectResponse(url=f"/ideajam/{existing.id}", status_code=status.HTTP_303_SEE_OTHER)

    # Create jam
    now = datetime.utcnow()
    jam = IdeaJam(
        team_id=team_id,
        started_by=current_user.id,
        started_at=now,
        ends_at=now + timedelta(minutes=JAM_DURATION_MINUTES),
        status=JamStatus.Active,
    )
    db.add(jam)
    await db.commit()
    await db.refresh(jam)

    return RedirectResponse(url=f"/ideajam/{jam.id}", status_code=status.HTTP_303_SEE_OTHER)


# ═══════════════════════════════════════════════════════════════
#  GET /ideajam/{jam_id} → render the jam page
# ═══════════════════════════════════════════════════════════════

@router.get("/{jam_id}", response_class=HTMLResponse)
async def jam_page(
    jam_id: int,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    jam_result = await db.execute(select(IdeaJam).where(IdeaJam.id == jam_id))
    jam = jam_result.scalar_one_or_none()
    if not jam:
        raise HTTPException(status_code=404, detail="Idea Jam not found")

    # Auto-complete if time is up
    now = datetime.utcnow()
    status_val = getattr(jam.status, 'value', jam.status)
    if status_val == "Active" and now >= jam.ends_at:
        jam.status = JamStatus.Completed
        await db.commit()

    # Fetch team name
    team_result = await db.execute(select(Team).where(Team.id == jam.team_id))
    team = team_result.scalar_one_or_none()

    # Survey checks
    has_submitted_survey = False
    teammates = []
    status_val = getattr(jam.status, 'value', jam.status)
    if status_val == "Completed":
        # Check if already submitted
        survey_res = await db.execute(select(JamSurvey).where(
            JamSurvey.jam_id == jam_id,
            JamSurvey.user_id == current_user.id
        ))
        if survey_res.scalar_one_or_none():
            has_submitted_survey = True

        # Fetch other teammates for the "avoid member" dropdown
        members_res = await db.execute(
            select(User)
            .join(TeamMembership, TeamMembership.user_id == User.id)
            .where(
                TeamMembership.team_id == jam.team_id,
                TeamMembership.left_at.is_(None),
                User.id != current_user.id
            )
        )
        teammates = members_res.scalars().all()

    return templates.TemplateResponse(
        "ideajam.html",
        {
            "request": request,
            "current_user": current_user,
            "jam": jam,
            "jam_status_str": getattr(jam.status, "value", jam.status),
            "team": team,
            "ends_at_iso": jam.ends_at.isoformat() + "Z",
            "has_submitted_survey": has_submitted_survey,
            "teammates": teammates,
        },
    )


# ═══════════════════════════════════════════════════════════════
#  GET /ideajam/{jam_id}/entries → JSON list of ideas (polling)
# ═══════════════════════════════════════════════════════════════

@router.get("/{jam_id}/entries", response_class=JSONResponse)
async def get_entries(
    jam_id: int,
    db: AsyncSession = Depends(get_db),
):
    jam_result = await db.execute(select(IdeaJam).where(IdeaJam.id == jam_id))
    jam = jam_result.scalar_one_or_none()
    if not jam:
        raise HTTPException(status_code=404, detail="Jam not found")

    # Auto-complete if expired
    now = datetime.utcnow()
    status_val = getattr(jam.status, 'value', jam.status)
    is_active = status_val == "Active" and now < jam.ends_at
    if status_val == "Active" and now >= jam.ends_at:
        jam.status = JamStatus.Completed
        await db.commit()
        is_active = False

    # Get entries with user names
    entries_result = await db.execute(
        select(IdeaJamEntry, User.full_name)
        .join(User, IdeaJamEntry.user_id == User.id)
        .where(IdeaJamEntry.jam_id == jam_id)
        .order_by(IdeaJamEntry.votes.desc(), IdeaJamEntry.id.asc())
    )
    entries = []
    for entry, full_name in entries_result.all():
        entries.append({
            "id": entry.id,
            "user_name": full_name,
            "idea_text": entry.idea_text,
            "votes": entry.votes,
        })

    return {"entries": entries, "is_active": is_active}


# ═══════════════════════════════════════════════════════════════
#  POST /ideajam/{jam_id}/submit → submit an idea
# ═══════════════════════════════════════════════════════════════

@router.post("/{jam_id}/submit", response_class=JSONResponse)
async def submit_idea(
    jam_id: int,
    idea_text: str = Form(...),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required")

    jam_result = await db.execute(select(IdeaJam).where(IdeaJam.id == jam_id))
    jam = jam_result.scalar_one_or_none()
    if not jam:
        raise HTTPException(status_code=404, detail="Jam not found")

    # Check jam is still active
    now = datetime.utcnow()
    status_val = getattr(jam.status, 'value', jam.status)
    if status_val != "Active" or now >= jam.ends_at:
        raise HTTPException(status_code=400, detail="This Idea Jam has ended")

    # Check membership
    if not await _check_team_member(db, current_user.id, jam.team_id):
        raise HTTPException(status_code=403, detail="Not a team member")

    # Truncate to 280 chars
    text = idea_text.strip()[:280]
    if not text:
        raise HTTPException(status_code=400, detail="Idea cannot be empty")

    entry = IdeaJamEntry(
        jam_id=jam_id,
        user_id=current_user.id,
        idea_text=text,
    )
    db.add(entry)
    await db.commit()

    return {"ok": True, "id": entry.id}


# ═══════════════════════════════════════════════════════════════
#  POST /ideajam/{jam_id}/vote/{entry_id} → upvote
# ═══════════════════════════════════════════════════════════════

@router.post("/{jam_id}/vote/{entry_id}", response_class=JSONResponse)
async def vote_idea(
    jam_id: int,
    entry_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required")

    entry_result = await db.execute(
        select(IdeaJamEntry).where(
            IdeaJamEntry.id == entry_id,
            IdeaJamEntry.jam_id == jam_id,
        )
    )
    entry = entry_result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Idea not found")

    entry.votes += 1
    await db.commit()

    return {"ok": True, "votes": entry.votes}


# ═══════════════════════════════════════════════════════════════
#  GET /ideajam/{jam_id}/results → ranked results page
# ═══════════════════════════════════════════════════════════════

@router.get("/{jam_id}/results", response_class=HTMLResponse)
async def results_page(
    jam_id: int,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    jam_result = await db.execute(select(IdeaJam).where(IdeaJam.id == jam_id))
    jam = jam_result.scalar_one_or_none()
    if not jam:
        raise HTTPException(status_code=404, detail="Jam not found")

    team_result = await db.execute(select(Team).where(Team.id == jam.team_id))
    team = team_result.scalar_one_or_none()

    # Survey checks
    has_submitted_survey = False
    teammates = []
    survey_res = await db.execute(select(JamSurvey).where(
        JamSurvey.jam_id == jam_id,
        JamSurvey.user_id == current_user.id
    ))
    if survey_res.scalar_one_or_none():
        has_submitted_survey = True
    else:
        members_res = await db.execute(
            select(User)
            .join(TeamMembership, TeamMembership.user_id == User.id)
            .where(
                TeamMembership.team_id == jam.team_id,
                TeamMembership.left_at.is_(None),
                User.id != current_user.id
            )
        )
        teammates = members_res.scalars().all()

    entries_result = await db.execute(
        select(IdeaJamEntry, User.full_name)
        .join(User, IdeaJamEntry.user_id == User.id)
        .where(IdeaJamEntry.jam_id == jam_id)
        .order_by(IdeaJamEntry.votes.desc(), IdeaJamEntry.id.asc())
    )
    entries = []
    for entry, full_name in entries_result.all():
        entries.append({
            "id": entry.id,
            "user_name": full_name,
            "idea_text": entry.idea_text,
            "votes": entry.votes,
        })

    return templates.TemplateResponse(
        "ideajam.html",
        {
            "request": request,
            "current_user": current_user,
            "jam": jam,
            "jam_status_str": getattr(jam.status, "value", jam.status),
            "team": team,
            "ends_at_iso": jam.ends_at.isoformat() + "Z",
            "has_submitted_survey": has_submitted_survey,
            "teammates": teammates,
        },
    )

# ═══════════════════════════════════════════════════════════════
#  POST /ideajam/{jam_id}/survey → submit post-jam survey
# ═══════════════════════════════════════════════════════════════

@router.post("/{jam_id}/survey", response_class=JSONResponse)
async def submit_jam_survey(
    jam_id: int,
    continue_in_team: bool = Form(...),
    avoid_member_id_str: Optional[str] = Form(None, alias="avoid_member_id"),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required")

    # Parse avoid_member_id manually because empty string from select causes 422
    avoid_member_id = None
    if avoid_member_id_str and avoid_member_id_str.strip():
        try:
            avoid_member_id = int(avoid_member_id_str)
        except ValueError:
            pass

    jam_result = await db.execute(select(IdeaJam).where(IdeaJam.id == jam_id))
    jam = jam_result.scalar_one_or_none()
    if not jam:
        raise HTTPException(status_code=404, detail="Jam not found")

    status_val = getattr(jam.status, 'value', jam.status)
    if status_val != "Completed":
        raise HTTPException(status_code=400, detail="Survey can only be filled out after the jam is completed.")

    # Check if a survey already exists
    survey_result = await db.execute(select(JamSurvey).where(
        JamSurvey.jam_id == jam_id,
        JamSurvey.user_id == current_user.id
    ))
    if survey_result.scalar_one_or_none():
         raise HTTPException(status_code=400, detail="Survey already submitted.")

    survey = JamSurvey(
        jam_id=jam_id,
        user_id=current_user.id,
        continue_in_team=continue_in_team,
        avoid_member_id=avoid_member_id if avoid_member_id and avoid_member_id > 0 else None
    )
    db.add(survey)
    await db.commit()

    return {"ok": True}

# ═══════════════════════════════════════════════════════════════
#  POST /ideajam/{jam_id}/finalize-team → form team from surveys
# ═══════════════════════════════════════════════════════════════

@router.post("/{jam_id}/finalize-team")
async def finalize_team(
    jam_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Team lead locks the team after reviewing Idea Jam survey results."""
    from datetime import datetime, timezone
    
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    # 1. Fetch Jam and verify completed
    jam_result = await db.execute(select(IdeaJam).where(IdeaJam.id == jam_id))
    jam = jam_result.scalar_one_or_none()
    if not jam:
        raise HTTPException(status_code=404, detail="Jam not found")
        
    status_val = getattr(jam.status, 'value', jam.status)
    if status_val != "Completed":
        raise HTTPException(status_code=400, detail="Jam must be completed to finalize.")

    # 2. Fetch Team and verify Lead
    team_result = await db.execute(select(Team).where(Team.id == jam.team_id))
    team = team_result.scalar_one_or_none()
    if not team or team.lead_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the team lead can finalize the team.")

    # 3. Fetch active memberships
    members_res = await db.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == team.id,
            TeamMembership.left_at.is_(None)
        )
    )
    memberships = {m.user_id: m for m in members_res.scalars().all()}

    # 4. Fetch survey results
    surveys_res = await db.execute(
        select(JamSurvey).where(JamSurvey.jam_id == jam_id)
    )
    surveys = surveys_res.scalars().all()
    
    users_to_remove = set()
    
    # 5. Process Opt-Outs (`continue_in_team == False`)
    for survey in surveys:
        if not survey.continue_in_team and survey.user_id != team.lead_id:
            users_to_remove.add(survey.user_id)
            
    # 6. Process Avoid flags (`avoid_member_id`)
    # If any remaining member flags User B, User B is removed (Lead is immune)
    for survey in surveys:
        avoid_id = survey.avoid_member_id
        # if the user who cast the vote is still on the team, and they flagged someone
        if avoid_id and survey.user_id not in users_to_remove:
            if avoid_id != team.lead_id and avoid_id in memberships:
                users_to_remove.add(avoid_id)

    # 7. Execute Removals
    now = datetime.now(timezone.utc)
    for u_id in users_to_remove:
        if u_id in memberships:
            memberships[u_id].left_at = now
            
    # 8. Lock Team (Status -> Active)
    team.status = TeamStatus.Active
    
    await db.commit()
    
    return RedirectResponse(
        url=f"/teams/{team.id}?success=Team+formation+finalized", 
        status_code=status.HTTP_303_SEE_OTHER
    )
