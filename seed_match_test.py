import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models.user import User
from app.models.hackathon import Hackathon
from app.models.team import Team

from sqlalchemy.orm import selectinload

async def setup():
    async with async_session() as db:
        users = (await db.execute(select(User).options(selectinload(User.capabilities)).limit(3))).scalars().all()
        u1 = users[1] 
        
        u1.linkedin_url = "https://linkedin.com/in/tech-developer-bob"
        await db.commit()
        await db.refresh(u1)
        
        hack = (await db.execute(select(Hackathon).where(Hackathon.id == 1))).scalar_one_or_none()
        if hack:
            caps = hack.required_capabilities or []
            if "Python" not in caps:
                caps.append("Python")
                hack.required_capabilities = caps
                await db.commit()
                
        from app.services.matching import score_user_for_team
        teams = (await db.execute(select(Team).limit(1))).scalars().all()
        if teams:
            score = score_user_for_team(u1, teams[0], hack, [])
            print(f"Candidate Match Score Details: {score}")

asyncio.run(setup())
