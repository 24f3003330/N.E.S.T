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
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, https_only=False)
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
