import asyncio
from sqlalchemy import select
from app.database import async_session_maker
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.models.user import User

async def main():
    async with async_session_maker() as db:
        res = await db.execute(select(User).limit(5))
        users = res.scalars().all()
        for u in users:
            print(f"User: {u.email} (ID: {u.id})")
            
            # test profile logic
            res_teams = await db.execute(
                select(Team)
                .join(TeamMembership, Team.id == TeamMembership.team_id)
                .where(
                    TeamMembership.user_id == u.id,
                    TeamMembership.left_at == None
                )
            )
            my_teams = res_teams.scalars().all()
            print(f"  Profile My Teams: {[t.name for t in my_teams]}")

asyncio.run(main())
