import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models.team import Team, TeamStatus
from app.models.team_membership import TeamMembership

async def main():
    async with async_session() as db:
        res_teams = await db.execute(
            select(Team)
            .join(TeamMembership, Team.id == TeamMembership.team_id)
            .where(
                TeamMembership.user_id == 1,
                TeamMembership.left_at == None
            )
        )
        teams1 = res_teams.scalars().all()
        print("Using == None:", [t.name for t in teams1])
        
        res_teams2 = await db.execute(
            select(Team)
            .join(TeamMembership, Team.id == TeamMembership.team_id)
            .where(
                TeamMembership.user_id == 1,
                TeamMembership.left_at.is_(None)
            )
        )
        teams2 = res_teams2.scalars().all()
        print("Using .is_(None):", [t.name for t in teams2])

if __name__ == "__main__":
    asyncio.run(main())
