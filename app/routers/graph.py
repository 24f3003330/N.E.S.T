"""Network graph router — collaboration network visualization."""

from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.capability import Capability
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/graph", tags=["graph"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def graph_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    """Render the network graph page."""
    return templates.TemplateResponse(
        "graph.html",
        {"request": request, "current_user": current_user},
    )


@router.get("/data", response_class=JSONResponse)
async def graph_data(db: AsyncSession = Depends(get_db)):
    """Return nodes and links JSON for D3 visualization."""

    # ── 1. Fetch all users with capabilities ──
    users_result = await db.execute(select(User))
    users = users_result.scalars().all()

    # Build user→capabilities map
    caps_result = await db.execute(select(Capability))
    all_caps = caps_result.scalars().all()
    user_caps: dict[int, list[str]] = defaultdict(list)
    for cap in all_caps:
        user_caps[cap.user_id].append(cap.name)

    # ── 2. Fetch all active memberships ──
    mem_result = await db.execute(
        select(TeamMembership.team_id, TeamMembership.user_id)
        .where(TeamMembership.left_at.is_(None))
    )
    memberships = mem_result.all()

    # team→list of user_ids
    team_members: dict[int, list[int]] = defaultdict(list)
    for team_id, user_id in memberships:
        team_members[team_id].append(user_id)

    # ── 3. Fetch team names ──
    teams_result = await db.execute(select(Team.id, Team.name))
    team_names = {tid: tname for tid, tname in teams_result.all()}

    # ── 4. Build links (user pairs sharing teams) ──
    pair_data: dict[tuple[int, int], dict] = {}
    for team_id, members in team_members.items():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = min(members[i], members[j]), max(members[i], members[j])
                key = (a, b)
                if key not in pair_data:
                    pair_data[key] = {"weight": 0, "teams": []}
                pair_data[key]["weight"] += 1
                pair_data[key]["teams"].append(team_names.get(team_id, "Unknown"))

    # ── 5. Count collaborations per user ──
    collab_count: dict[int, int] = defaultdict(int)
    for (a, b), info in pair_data.items():
        collab_count[a] += info["weight"]
        collab_count[b] += info["weight"]

    # ── 6. Build nodes list ──
    nodes = []
    for user in users:
        nodes.append({
            "id": user.id,
            "name": user.full_name,
            "archetype": getattr(user.archetype, 'value', user.archetype) if user.archetype else "Unknown",
            "department": user.department or "Unknown",
            "capabilities": user_caps.get(user.id, [])[:5],
            "capability_count": len(user_caps.get(user.id, [])),
            "collab_count": collab_count.get(user.id, 0),
        })

    # ── 7. Build links list ──
    links = []
    for (source, target), info in pair_data.items():
        links.append({
            "source": source,
            "target": target,
            "weight": info["weight"],
            "team_name": ", ".join(info["teams"]),
        })

    return {"nodes": nodes, "links": links}
