import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models.team_invitation import TeamInvitation

async def main():
    async with async_session() as db:
        res = await db.execute(select(TeamInvitation))
        invites = res.scalars().all()
        for i in invites:
            print(f"Invite ID: {i.id}, Team: {i.team_id}, From: {i.from_user_id}, To: {i.to_user_id}")

asyncio.run(main())
