"""
Profile router — view / edit profiles, manage capabilities.

Endpoints:
    GET  /profile              → own profile (redirect to login if anonymous)
    GET  /profile/{user_id}    → another user's profile
    POST /profile/update       → update bio, archetype, linkedin, github
    POST /profile/capabilities/add           → add a capability
    DELETE /profile/capabilities/{cap_id}    → remove a capability
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.capability import Capability, CategoryEnum, ProficiencyEnum
from app.models.user import ArchetypeEnum, User, AccountTypeEnum
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.models.rating import Rating
from app.routers.auth import get_current_user

router = APIRouter(prefix="/profile", tags=["profile"])
templates = Jinja2Templates(directory="app/templates")

# ── Category → Bootstrap colour mapping (passed to the template) ──
CATEGORY_COLORS = {
    "Technical": "primary",
    "Design": "purple",
    "Domain": "success",
    "Soft Skill": "warning",
}


def _group_capabilities(capabilities: List[Capability]) -> Dict[str, List[Capability]]:
    """Group a list of capabilities by their category value."""
    grouped: Dict[str, List[Capability]] = {}
    for cap in capabilities:
        key = getattr(cap.category, 'value', cap.category)  # e.g. "Technical"
        grouped.setdefault(key, []).append(cap)
    return grouped


async def _load_user_with_caps(db: AsyncSession, user_id: int) -> Optional[User]:
    """Load a user together with their capabilities in one query."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.capabilities))
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()


# ═══════════════════════════════════════════════════════════════
#  GET /profile — own profile
# ═══════════════════════════════════════════════════════════════

@router.get("/", response_class=HTMLResponse)
async def own_profile(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    user = await _load_user_with_caps(db, current_user.id)
    grouped = _group_capabilities(user.capabilities)
    
    # Fetch user's active teams via manual join
    res_teams = await db.execute(
        select(Team)
        .join(TeamMembership, Team.id == TeamMembership.team_id)
        .where(
            TeamMembership.user_id == current_user.id,
            TeamMembership.left_at == None
        )
    )
    my_teams = res_teams.scalars().all()

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user,
            "is_owner": True,
            "grouped_caps": grouped,
            "category_colors": CATEGORY_COLORS,
            "archetypes": [a.value for a in ArchetypeEnum],
            "categories": [c.value for c in CategoryEnum],
            "proficiencies": [p.value for p in ProficiencyEnum],
            "current_user": current_user,
            "my_teams": my_teams,
            "errors": [],
            "success": request.query_params.get("success", ""),
        },
    )


# ═══════════════════════════════════════════════════════════════
#  GET /profile/{user_id} — another user's profile
# ═══════════════════════════════════════════════════════════════

@router.get("/{user_id}", response_class=HTMLResponse)
async def view_profile(
    user_id: int,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await _load_user_with_caps(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_owner = current_user is not None and current_user.id == user.id
    grouped = _group_capabilities(user.capabilities)

    # Fetch user's active teams via manual join
    res_teams = await db.execute(
        select(Team)
        .join(TeamMembership, Team.id == TeamMembership.team_id)
        .where(
            TeamMembership.user_id == user.id,
            TeamMembership.left_at == None
        )
    )
    my_teams = res_teams.scalars().all()
    
    # Calculate Average Rating if not the owner
    average_rating = 0.0
    rating_count = 0
    if not is_owner:
        try:
            from sqlalchemy import func
            res_rating = await db.execute(
                select(
                    func.avg(Rating.score).label("avg_score"),
                    func.count(Rating.id).label("count")
                )
                .where(Rating.ratee_id == user.id)
            )
            row = res_rating.fetchone()
            if row and row.avg_score is not None:
                average_rating = round(float(row.avg_score), 1)
                rating_count = row.count
        except Exception as e:
            print(f"Error calculating ratings: {e}")

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user,
            "is_owner": is_owner,
            "grouped_caps": grouped,
            "category_colors": CATEGORY_COLORS,
            "archetypes": [a.value for a in ArchetypeEnum],
            "categories": [c.value for c in CategoryEnum],
            "proficiencies": [p.value for p in ProficiencyEnum],
            "current_user": current_user,
            "my_teams": my_teams,
            "average_rating": average_rating,
            "rating_count": rating_count,
            "errors": [],
            "success": request.query_params.get("success", ""),
        },
    )


# ═══════════════════════════════════════════════════════════════
#  POST /profile/update — update bio, archetype, socials
# ═══════════════════════════════════════════════════════════════

@router.post("/update", response_class=HTMLResponse)
async def update_profile(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    form = await request.form()

    current_user.bio = form.get("bio", "").strip() or None
    current_user.linkedin_url = form.get("linkedin_url", "").strip() or None
    current_user.github_username = form.get("github_username", "").strip() or None
    current_user.year_of_study = int(form.get("year_of_study") or 0) or None

    archetype_val = form.get("archetype", "").strip()
    if archetype_val:
        try:
            current_user.archetype = ArchetypeEnum(archetype_val)
        except ValueError:
            pass
    else:
        current_user.archetype = None

    account_type_val = form.get("account_type", "").strip()
    if account_type_val:
        try:
            current_user.account_type = AccountTypeEnum(account_type_val)
        except ValueError:
            pass

    await db.flush()
    return RedirectResponse(
        url="/profile?success=Profile+updated", status_code=status.HTTP_303_SEE_OTHER
    )


# ═══════════════════════════════════════════════════════════════
#  POST /profile/capabilities/add
# ═══════════════════════════════════════════════════════════════

@router.post("/capabilities/add", response_class=HTMLResponse)
async def add_capability(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    form = await request.form()
    name = form.get("cap_name", "").strip()
    category_val = form.get("cap_category", "").strip()
    proficiency_val = form.get("cap_proficiency", "").strip()

    if not name or not category_val:
        return RedirectResponse(
            url="/profile?error=Name+and+category+are+required",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        category = CategoryEnum(category_val)
    except ValueError:
        category = CategoryEnum.TECHNICAL

    try:
        proficiency = ProficiencyEnum(proficiency_val)
    except ValueError:
        proficiency = ProficiencyEnum.BEGINNER

    cap = Capability(
        name=name,
        category=category,
        proficiency_level=proficiency,
        user_id=current_user.id,
    )
    db.add(cap)
    await db.flush()

    return RedirectResponse(
        url="/profile?success=Capability+added", status_code=status.HTTP_303_SEE_OTHER
    )


# ═══════════════════════════════════════════════════════════════
#  DELETE /profile/capabilities/{cap_id}  (POST fallback for forms)
# ═══════════════════════════════════════════════════════════════

@router.post("/capabilities/{cap_id}/delete", response_class=HTMLResponse)
async def delete_capability(
    cap_id: int,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    result = await db.execute(select(Capability).where(Capability.id == cap_id))
    cap = result.scalar_one_or_none()

    if not cap or cap.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    await db.delete(cap)
    await db.flush()

    return RedirectResponse(
        url="/profile?success=Capability+removed", status_code=status.HTTP_303_SEE_OTHER
    )
