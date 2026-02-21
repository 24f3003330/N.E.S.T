"""Teams router – full team formation system with HTML templates."""

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.chat_room import ChatRoom
from app.models.hackathon import Hackathon
from app.models.project import Project
from app.models.team import Team, TeamStatus
from app.models.team_invitation import InvitationDirection, InvitationStatus, TeamInvitation
from app.models.team_membership import Role, TeamMembership
from app.models.user import User
from app.models.rating import Rating
from app.routers.auth import get_current_user
from app.services.notifications import send_invitation_email, send_join_request_email

router = APIRouter(prefix="/teams", tags=["teams"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def list_teams(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all teams."""
    # 1. Fetch Forming teams for discovery
    result = await db.execute(select(Team).where(Team.status == TeamStatus.Forming))
    discover_teams = result.scalars().all()

    # 2. Fetch My Teams
    my_teams = []
    if current_user:
        res_mine = await db.execute(
            select(Team)
            .join(TeamMembership, Team.id == TeamMembership.team_id)
            .where(
                TeamMembership.user_id == current_user.id,
                TeamMembership.left_at.is_(None)
            )
        )
        my_teams = res_mine.scalars().all()
        # Remove My Teams from Discover Teams
        my_team_ids = {t.id for t in my_teams}
        discover_teams = [t for t in discover_teams if t.id not in my_team_ids]

    return templates.TemplateResponse(
        "teams_list.html",
        {
            "request": request, 
            "discover_teams": discover_teams, 
            "my_teams": my_teams,
            "current_user": current_user
        },
    )


from app.models.user import AccountTypeEnum

@router.get("/create", response_class=HTMLResponse)
async def create_team_form(
    request: Request,
    hackathon_id: Optional[int] = None,
    project_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_current_user),
):
    """Show the team creation form."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    if current_user.account_type != AccountTypeEnum.LEADER:
        raise HTTPException(status_code=403, detail="Only Leaders can create teams.")
    return templates.TemplateResponse(
        "team_create.html",
        {
            "request": request,
            "current_user": current_user,
            "hackathon_id": hackathon_id,
            "project_id": project_id,
        },
    )


@router.post("/create")
async def create_team(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    max_size: Optional[int] = Form(None),
    hackathon_id: Optional[int] = Form(None),
    project_id: Optional[int] = Form(None),
    github_repo_url: Optional[str] = Form(None),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new team, add lead, create ChatRoom."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    if current_user.account_type != AccountTypeEnum.LEADER:
        raise HTTPException(status_code=403, detail="Only Leaders can create teams.")

    # 1. Create Team
    team = Team(
        name=name,
        description=description,
        lead_id=current_user.id,
        hackathon_id=hackathon_id,
        project_id=project_id,
        max_size=max_size,
        github_repo_url=github_repo_url,
    )
    db.add(team)
    await db.flush()  # to get team.id

    # 2. Add creator as Lead
    membership = TeamMembership(
        team_id=team.id,
        user_id=current_user.id,
        role=Role.Lead,
    )
    db.add(membership)

    # 3. Create ChatRoom
    chat_room = ChatRoom(team_id=team.id)
    db.add(chat_room)

    await db.commit()
    return RedirectResponse(url=f"/teams/{team.id}?success=Team+created+successfully", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{team_id}", response_class=HTMLResponse)
async def team_detail(
    request: Request,
    team_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Show team detail, members, and pending invitations."""
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Fetch context
    hackathon_title = None
    if team.hackathon_id:
        hack = await db.execute(select(Hackathon).where(Hackathon.id == team.hackathon_id))
        h = hack.scalar_one_or_none()
        if h: hackathon_title = h.title
        
    project_title = None
    if team.project_id:
        proj = await db.execute(select(Project).where(Project.id == team.project_id))
        p = proj.scalar_one_or_none()
        if p: project_title = p.title

    # Fetch members with User data
    members_result = await db.execute(
        select(TeamMembership, User)
        .join(User, TeamMembership.user_id == User.id)
        .where(TeamMembership.team_id == team_id, TeamMembership.left_at.is_(None))
    )
    members = members_result.all()  # List of tuples (TeamMembership, User)

    # Fetch pending invitations (both requests to join AND invites sent to the current user)
    # We fetch all pending invitations for this team
    invites_result = await db.execute(
        select(TeamInvitation)
        .where(
            TeamInvitation.team_id == team_id,
            TeamInvitation.status == InvitationStatus.Pending
        )
    )
    all_pending_invites = invites_result.scalars().all()

    # Split them up for the template
    pending_requests = []
    pending_sent_invites = []
    my_pending_invite = None
    
    if all_pending_invites:
        # For requests, we need the User info of the requester (from_user_id)
        requester_ids = [inv.from_user_id for inv in all_pending_invites if getattr(inv.direction, 'value', inv.direction) == "Request"]
        
        # For sent invites, we need the User info of the invitee (to_user_id)
        invitee_ids = [inv.to_user_id for inv in all_pending_invites if getattr(inv.direction, 'value', inv.direction) == "Invite"]

        user_lookup = {}
        all_needed_users = list(set(requester_ids + invitee_ids))
        if all_needed_users:
            req_users = await db.execute(select(User).where(User.id.in_(all_needed_users)))
            user_lookup = {u.id: u for u in req_users.scalars().all()}
            
        for inv in all_pending_invites:
            inv_dir = getattr(inv.direction, 'value', inv.direction)
            if inv_dir == "Request":
                if inv.from_user_id in user_lookup:
                    pending_requests.append((inv, user_lookup[inv.from_user_id]))
            elif inv_dir == "Invite":
                if current_user and inv.to_user_id == current_user.id:
                    my_pending_invite = inv
                if inv.to_user_id in user_lookup:
                    pending_sent_invites.append((inv, user_lookup[inv.to_user_id]))

    # Determine the current user's role on the team
    user_role = None
    if current_user:
        for mem, _ in members:
            if mem.user_id == current_user.id:
                user_role = getattr(mem.role, 'value', mem.role)
                break

    # ━━━ Pending Peer Evaluations logic ━━━
    # If the team is 'Completed' and the user is a member, find who they haven't rated
    pending_evals = []
    if current_user and user_role and team.status == TeamStatus.Completed:
        # Get all users the current user HAS rated for this team
        res_rated = await db.execute(
            select(Rating.ratee_id).where(
                Rating.team_id == team.id,
                Rating.rater_id == current_user.id
            )
        )
        rated_ids = {r for r in res_rated.scalars()}
        
        # Build list of members NOT YET rated (excluding self)
        for mem, usr in members:
            if usr.id != current_user.id and usr.id not in rated_ids:
                pending_evals.append((mem, usr))

    return templates.TemplateResponse(
        "team_detail.html",
        {
            "request": request,
            "current_user": current_user,
            "team": team,
            "hackathon_title": hackathon_title,
            "project_title": project_title,
            "members": members,
            "pending_requests": pending_requests,
            "pending_sent_invites": pending_sent_invites,
            "my_pending_invite": my_pending_invite,
            "user_role": user_role,
            "pending_evals": pending_evals,
        },
    )


@router.post("/{team_id}/invite")
async def invite_member(
    team_id: int,
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    message: Optional[str] = Form(None),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lead invites a user by email."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    team_result = await db.execute(select(Team).where(Team.id == team_id))
    team = team_result.scalar_one_or_none()
    if not team or team.lead_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only team lead can invite.")

    user_result = await db.execute(select(User).where(User.email == email))
    invitee = user_result.scalar_one_or_none()
    if not invitee:
        # We could use flashing here, but for now simple return
        return RedirectResponse(url=f"/teams/{team_id}?error=User not found", status_code=status.HTTP_303_SEE_OTHER)

    inv = TeamInvitation(
        team_id=team_id,
        from_user_id=current_user.id,
        to_user_id=invitee.id,
        direction=InvitationDirection.Invite,
        message=message,
    )
    db.add(inv)

    # ── In-app notification for the invitee ──
    from app.models.notification import Notification
    notif = Notification(
        user_id=invitee.id,
        message=f"📩 {current_user.full_name} invited you to join <b>{team.name}</b>",
        link=f"/teams/{team_id}",
    )
    db.add(notif)
    await db.commit()
    
    background_tasks.add_task(
        send_invitation_email,
        recipient_email=invitee.email,
        team_name=team.name,
        lead_name=current_user.full_name,
        message=message
    )
    
    return RedirectResponse(url=f"/teams/{team_id}?success=Invitation+sent+successfully", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/request/{team_id}")
async def request_to_join(
    team_id: int,
    background_tasks: BackgroundTasks,
    message: Optional[str] = Form(None),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Member requests to join a team."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    team_result = await db.execute(select(Team).where(Team.id == team_id))
    team = team_result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found.")

    inv = TeamInvitation(
        team_id=team_id,
        from_user_id=current_user.id,
        to_user_id=team.lead_id,
        direction=InvitationDirection.Request,
        message=message,
    )
    db.add(inv)

    # ── In-app notification for the team lead ──
    from app.models.notification import Notification
    notif = Notification(
        user_id=team.lead_id,
        message=f"🙋 {current_user.full_name} requested to join <b>{team.name}</b>",
        link=f"/teams/{team_id}",
    )
    db.add(notif)
    await db.commit()
    
    lead_result = await db.execute(select(User).where(User.id == team.lead_id))
    lead = lead_result.scalar_one_or_none()
    if lead:
        background_tasks.add_task(
            send_join_request_email,
            recipient_email=lead.email,
            team_name=team.name,
            requester_name=current_user.full_name,
            message=message
        )
        
    return RedirectResponse(url=f"/teams/{team_id}?success=Join+request+sent+successfully", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/invitation/{inv_id}/respond")
async def respond_invitation(
    inv_id: int,
    action: str = Form(...),  # 'accept' or 'decline'
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Respond to an invite or request."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    inv_result = await db.execute(select(TeamInvitation).where(TeamInvitation.id == inv_id))
    inv = inv_result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found.")

    team_result = await db.execute(select(Team).where(Team.id == inv.team_id))
    team = team_result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found.")

    # Only to_user_id can respond, OR the sender can decline (revoke)
    is_recipient = (inv.to_user_id == current_user.id)
    is_sender = (inv.from_user_id == current_user.id)
    
    if not (is_recipient or (is_sender and action == "decline")):
        raise HTTPException(status_code=403, detail="Not authorized to respond to this invitation.")

    if action == "accept":
        try:
            inv.status = InvitationStatus.Accepted
            inv_dir = str(getattr(inv.direction, 'value', inv.direction))
            new_member_id = inv.to_user_id if inv_dir == "Invite" else inv.from_user_id
            
            mem_check = await db.execute(
                select(TeamMembership).where(
                    TeamMembership.team_id == inv.team_id,
                    TeamMembership.user_id == new_member_id
                )
            )
            existing_mem = mem_check.scalar_one_or_none()
            
            if not (existing_mem and existing_mem.left_at is None):
                current_members_result = await db.execute(
                    select(func.count(TeamMembership.user_id)).where(
                        TeamMembership.team_id == inv.team_id,
                        TeamMembership.left_at.is_(None)
                    )
                )
                current_count = current_members_result.scalar() or 0
                if team.max_size is not None and current_count >= team.max_size:
                    raise HTTPException(status_code=400, detail="Team is already at maximum capacity.")
                    
                if existing_mem:
                    existing_mem.left_at = None
                    existing_mem.joined_at = func.now()
                else:
                    membership = TeamMembership(team_id=inv.team_id, user_id=new_member_id, role=Role.Member)
                    db.add(membership)
                
            from app.models.notification import Notification
            team_result2 = await db.execute(select(Team).where(Team.id == inv.team_id))
            team_for_notif = team_result2.scalar_one_or_none()
            team_name = team_for_notif.name if (team_for_notif and getattr(team_for_notif, 'name', None)) else "the team"
            user_name = current_user.full_name if getattr(current_user, 'full_name', None) else "A user"

            other_user_id = inv.from_user_id if is_recipient else inv.to_user_id
            
            notif = Notification(
                user_id=other_user_id,
                message=f"✅ {user_name} accepted your request/invite for <b>{team_name}</b>",
                link=f"/teams/{inv.team_id}",
            )
            db.add(notif)
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error during accept: {str(e)}")

    elif action == "decline":
        try:
            inv.status = InvitationStatus.Declined
            
            from app.models.notification import Notification
            team_result2 = await db.execute(select(Team).where(Team.id == inv.team_id))
            team_for_notif = team_result2.scalar_one_or_none()
            team_name = team_for_notif.name if (team_for_notif and getattr(team_for_notif, 'name', None)) else "the team"
            user_name = current_user.full_name if getattr(current_user, 'full_name', None) else "A user"

            other_user_id = inv.from_user_id if is_recipient else inv.to_user_id
            
            notif = Notification(
                user_id=other_user_id,
                message=f"❌ {user_name} declined/revoked the request/invite for <b>{team_name}</b>",
                link=f"/teams/{inv.team_id}",
            )
            db.add(notif)
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error during decline: {str(e)}")

    return RedirectResponse(url=f"/teams/{inv.team_id}?success=Response+submitted+successfully", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{team_id}/leave")
async def leave_team(
    team_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Member leaves the team."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    from datetime import datetime, timezone
    mem_result = await db.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == current_user.id,
            TeamMembership.left_at.is_(None)
        )
    )
    membership = mem_result.scalar_one_or_none()
    if membership:
        membership.left_at = datetime.now(timezone.utc)
        await db.commit()

    return RedirectResponse(url="/hackathons/dashboard?success=You+have+left+the+team", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/{team_id}/lock")
async def lock_team(
    team_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lead locks the team to stop it from appearing in public searches."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    team_result = await db.execute(select(Team).where(Team.id == team_id))
    team = team_result.scalar_one_or_none()
    
    if not team or team.lead_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only team lead can lock the team.")
        
    team.status = TeamStatus.Active
    await db.commit()
    
    return RedirectResponse(url=f"/teams/{team_id}?success=Team+locked+successfully", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/{team_id}/delete")
async def delete_team(
    team_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lead deletes the team permanently."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    team_result = await db.execute(select(Team).where(Team.id == team_id))
    team = team_result.scalar_one_or_none()
    
    if not team or team.lead_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only team lead can delete the team.")

    from app.models.message import Message
    
    # Optional cascade-like cleanup
    # 1. Delete Messages and ChatRooms
    chatrooms = await db.execute(select(ChatRoom).where(ChatRoom.team_id == team_id))
    for room in chatrooms.scalars().all():
        await db.execute(Message.__table__.delete().where(Message.chat_room_id == room.id))
    await db.execute(ChatRoom.__table__.delete().where(ChatRoom.team_id == team_id))
    
    # 2. Delete Invitations and Requests
    await db.execute(TeamInvitation.__table__.delete().where(TeamInvitation.team_id == team_id))
    
    from app.models.request import JoinRequest
    await db.execute(JoinRequest.__table__.delete().where(JoinRequest.team_id == team_id))
    
    await db.execute(Rating.__table__.delete().where(Rating.team_id == team_id))
    
    # 3. Delete Memberships
    await db.execute(TeamMembership.__table__.delete().where(TeamMembership.team_id == team_id))
    
    # 4. Delete Team
    await db.delete(team)
    await db.commit()
    
    return RedirectResponse(
        url=f"/teams?success=Team+dissolved+successfully", status_code=status.HTTP_303_SEE_OTHER
    )


# ═══════════════════════════════════════════════════════════════
#  POST /teams/{team_id}/rate/{ratee_id} => Submit Peer Rating
# ═══════════════════════════════════════════════════════════════

@router.post("/{team_id}/rate/{ratee_id}", response_class=HTMLResponse)
async def submit_team_rating(
    team_id: int,
    ratee_id: int,
    score: int = Form(...),
    feedback: Optional[str] = Form(None),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a star rating and feedback for a teammate after a project ends."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    # 1. Verify team is Completed
    team_res = await db.execute(select(Team).where(Team.id == team_id))
    team = team_res.scalar_one_or_none()
    if not team or team.status != TeamStatus.Completed:
        raise HTTPException(status_code=400, detail="Team must be completed to submit ratings.")

    # 2. Verify rater is actually on the team
    rater_mem_res = await db.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == current_user.id
        )
    )
    if not rater_mem_res.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You must be on the team to rate members.")

    # 3. Verify ratee is actually on the team
    ratee_mem_res = await db.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == ratee_id
        )
    )
    if not ratee_mem_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="The rated user is not on this team.")

    if current_user.id == ratee_id:
        raise HTTPException(status_code=400, detail="You cannot rate yourself.")

    # 4. Save rating
    # Enforce score bounds 1-5
    actual_score = max(1.0, min(5.0, float(score)))

    # Check for existing rating to update or insert
    existing_res = await db.execute(
        select(Rating).where(
            Rating.team_id == team_id,
            Rating.rater_id == current_user.id,
            Rating.ratee_id == ratee_id
        )
    )
    existing = existing_res.scalar_one_or_none()

    if existing:
        existing.score = actual_score
        existing.feedback = feedback
    else:
        new_rating = Rating(
            team_id=team_id,
            rater_id=current_user.id,
            ratee_id=ratee_id,
            score=actual_score,
            feedback=feedback,
        )
        db.add(new_rating)

    await db.commit()
    return RedirectResponse(
        url=f"/teams/{team_id}?success=Evaluation+submitted", status_code=status.HTTP_303_SEE_OTHER
    )


# ═══════════════════════════════════════════════════════════════
#  POST /teams/{team_id}/create-repo → GitHub repo auto-creation
# ═══════════════════════════════════════════════════════════════

@router.post("/{team_id}/create-repo")
async def create_repo(
    team_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Team lead creates a GitHub repo for the team."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    # Verify team exists
    team_result = await db.execute(select(Team).where(Team.id == team_id))
    team = team_result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Verify user is team lead
    mem_result = await db.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == current_user.id,
            TeamMembership.left_at.is_(None),
        )
    )
    membership = mem_result.scalar_one_or_none()
    if not membership or getattr(membership.role, 'value', membership.role) != "Lead":
        raise HTTPException(status_code=403, detail="Only the team lead can create a repo")

    # Verify no repo exists yet
    if team.github_repo_url:
        return RedirectResponse(url=f"/teams/{team_id}?success=Rating+submitted+successfully", status_code=status.HTTP_303_SEE_OTHER)

    # Verify minimum 2 members
    count_result = await db.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.left_at.is_(None),
        )
    )
    all_members = count_result.scalars().all()
    if len(all_members) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 members to create a repo")

    # Collect github usernames from all active members
    member_ids = [m.user_id for m in all_members]
    users_result = await db.execute(select(User).where(User.id.in_(member_ids)))
    users = users_result.scalars().all()
    github_usernames = [u.github_username for u in users if u.github_username]

    # Fetch hackathon name if linked
    hack_name = None
    if team.hackathon_id:
        hack_result = await db.execute(select(Hackathon).where(Hackathon.id == team.hackathon_id))
        h = hack_result.scalar_one_or_none()
        if h:
            hack_name = h.title

    # Create repo
    from app.services.github_service import create_team_repo
    try:
        repo_url = create_team_repo(
            team_name=team.name,
            description=team.description or "",
            member_github_usernames=github_usernames,
            hackathon_name=hack_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub API error: {str(e)}")

    # Save repo URL
    team.github_repo_url = repo_url
    await db.commit()

    # Post bot message in team chat
    from app.models.chat_room import ChatRoom
    from app.models.message import Message

    room_result = await db.execute(select(ChatRoom).where(ChatRoom.team_id == team_id))
    room = room_result.scalar_one_or_none()
    if room:
        bot_msg = Message(
            chat_room_id=room.id,
            sender_id=current_user.id,
            content=f"🚀 <b>Your GitHub repo is ready!</b><br>"
                    f"<a href='{repo_url}' target='_blank'>{repo_url}</a>",
            is_bot=True,
        )
        db.add(bot_msg)
        await db.commit()

        # Broadcast to connected WebSocket clients
        try:
            from app.routers.chat import manager
            await db.refresh(bot_msg)
            await manager.broadcast({
                "id": bot_msg.id,
                "content": bot_msg.content,
                "timestamp": bot_msg.created_at.isoformat(),
                "sender_id": 0,
                "sender_name": "N.E.S.T Bot",
                "is_bot": True,
            }, room.id)
        except Exception:
            pass  # WebSocket broadcast is best-effort

    return RedirectResponse(url=f"/teams/{team_id}?success=GitHub+repo+created+successfully", status_code=status.HTTP_303_SEE_OTHER)
