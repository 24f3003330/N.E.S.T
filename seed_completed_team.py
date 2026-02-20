import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models.user import User
from app.models.team import Team, TeamStatus
from app.models.team_membership import TeamMembership, Role

async def setup():
    async with async_session() as db:
        # Get first two users
        users = (await db.execute(select(User).limit(2))).scalars().all()
        if len(users) < 2:
            print("Not enough users")
            return
            
        u1, u2 = users[0], users[1]
        
        # Check if team exists
        team = (await db.execute(select(Team).limit(1))).scalar_one_or_none()
        if not team:
            team = Team(name="Alpha Strike", lead_id=u1.id, status=TeamStatus.Completed)
            db.add(team)
            await db.commit()
            
            m1 = TeamMembership(team_id=team.id, user_id=u1.id, role=Role.Lead)
            m2 = TeamMembership(team_id=team.id, user_id=u2.id, role=Role.Member)
            db.add_all([m1, m2])
            await db.commit()
        else:
            team.status = TeamStatus.Completed
            await db.commit()
            
            # Ensure both users are on team
            m1 = (await db.execute(select(TeamMembership).where(TeamMembership.team_id == team.id, TeamMembership.user_id == u1.id))).scalar_one_or_none()
            if not m1:
                db.add(TeamMembership(team_id=team.id, user_id=u1.id, role=Role.Lead))
            m2 = (await db.execute(select(TeamMembership).where(TeamMembership.team_id == team.id, TeamMembership.user_id == u2.id))).scalar_one_or_none()
            if not m2:
                db.add(TeamMembership(team_id=team.id, user_id=u2.id, role=Role.Member))
            await db.commit()
            
        print(f"Team {team.id} is Completed.")
        print(f"Members: {u1.email}, {u2.email}")

asyncio.run(setup())
