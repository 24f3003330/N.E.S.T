"""
N.E.S.T — FastAPI application entry-point.

Run with:
    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import settings
from app.database import Base, engine

# ── Import routers ──
from app.routers import auth, chat, graph, hackathons, ideajam, matching, notifications, profile, teams, users


# ── Lifespan: create tables on startup ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Campus Collaboration Platform — find teammates, build projects, win hackathons.",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Session middleware (required for OAuth state) ──
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, https_only=not settings.DEBUG)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=("*",))

# ── Static files & templates ──
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ── Register API routers ──
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(teams.router)
app.include_router(hackathons.router)
app.include_router(chat.router)
app.include_router(matching.router)
app.include_router(profile.router)
app.include_router(graph.router)
app.include_router(ideajam.router)
app.include_router(notifications.router)

import os
if os.environ.get("ENVIRONMENT") != "production":
    from fastapi.responses import RedirectResponse
    from app.routers.auth import _set_auth_cookie
    
    @app.get("/mock-login/{user_id}")
    def mock_login(user_id: int):
        resp = RedirectResponse(url="/hackathons/dashboard", status_code=303)
        return _set_auth_cookie(resp, user_id)

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.hackathon import Hackathon
from app.models.project import Project
from app.models.team import Team
from app.models.user import User
from app.routers.auth import get_current_user

@app.get("/dev/seed-hackathons")
async def dev_seed_hackathons(db: AsyncSession = Depends(get_db)):
    import json
    from datetime import datetime, timedelta, timezone
    
    # Get any user to be the creator
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    
    if not user:
        return {"status": "error", "detail": "No users found in the database. Please register a user first."}

    now = datetime.now(timezone.utc)

    hackathons = [
        Hackathon(
            title="Global AI Challenge 2026",
            description="Build the next generation of LLM applications to solve real-world problems. Focus areas include healthcare, education, and climate tech.",
            organizer="OpenAI & Microsoft",
            created_by=user.id,
            start_date=now + timedelta(days=5),
            end_date=now + timedelta(days=7),
            registration_deadline=now + timedelta(days=3),
            max_team_size=4,
            min_team_size=2,
            required_capabilities_json=json.dumps(["Python", "Machine Learning", "React", "UI/UX Design"]),
            tags_json=json.dumps(["AI", "Healthcare", "Education"]),
            status="Upcoming"
        ),
        Hackathon(
            title="Smart Campus IoT Hack",
            description="Join us to make our university campus smarter, greener, and more connected using IoT devices and data analytics.",
            organizer="University Tech Board",
            created_by=user.id,
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=1),
            registration_deadline=now - timedelta(days=2),
            max_team_size=5,
            min_team_size=3,
            required_capabilities_json=json.dumps(["C++", "Python", "Data Analysis", "Project Management"]),
            tags_json=json.dumps(["IoT", "Smart Campus", "Green Tech"]),
            status="Active"
        ),
        Hackathon(
            title="FinTech Disruptors Buildathon",
            description="Redefine the future of finance. Build decentralized applications, payment gateways, and innovative banking solutions.",
            organizer="Stripe & Plaid",
            created_by=user.id,
            start_date=now - timedelta(days=10),
            end_date=now - timedelta(days=8),
            registration_deadline=now - timedelta(days=12),
            max_team_size=4,
            min_team_size=1,
            required_capabilities_json=json.dumps(["Solidity", "Node.js", "Financial Modeling", "Figma"]),
            tags_json=json.dumps(["FinTech", "Web3", "Blockchain"]),
            status="Completed"
        )
    ]

    for h in hackathons:
        db.add(h)
    
    await db.commit()
    return {"status": "success", "detail": "Successfully seeded 3 mock hackathons (1 Upcoming, 1 Active, 1 Completed)."}


# ── Landing page ──
@app.get("/")
async def homepage(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Fetch live stats
    users_count = (await db.execute(select(func.count(User.id)))).scalar() or 0
    hacks_count = (await db.execute(select(func.count(Hackathon.id)))).scalar() or 0
    proj_count = (await db.execute(select(func.count(Project.id)))).scalar() or 0
    teams_count = (await db.execute(select(func.count(Team.id)))).scalar() or 0

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "current_user": current_user,
            "stats": {
                "users": users_count,
                "hackathons": hacks_count,
                "projects": proj_count,
                "teams": teams_count,
            },
        },
    )
