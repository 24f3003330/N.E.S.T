import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from app.database import async_session
from app.models.user import User
from app.models.team import Team, TeamStatus
from app.models.team_membership import TeamMembership
from app.models.idea_jam import IdeaJam, JamStatus
from app.models.jam_survey import JamSurvey

async def setup():
    async with async_session() as db:
        users = (await db.execute(select(User).limit(3))).scalars().all()
        u1, u2, u3 = users[0], users[1], users[2]
        # u1 is lead. u2 is Member 1. u3 is Member 2.
        
        team = Team(
            name="Formation Test Team",
            description="Test",
            hackathon_id=1,
            lead_id=u1.id,
            status=TeamStatus.Forming
        )
        db.add(team)
        await db.commit()
        await db.refresh(team)
        
        m1 = TeamMembership(team_id=team.id, user_id=u1.id)
        m2 = TeamMembership(team_id=team.id, user_id=u2.id)
        m3 = TeamMembership(team_id=team.id, user_id=u3.id)
        db.add_all([m1, m2, m3])
        await db.commit()
        
        jam = IdeaJam(
            team_id=team.id,
            started_by=u1.id,
            status=JamStatus.Completed,
            ends_at=datetime.utcnow() - timedelta(minutes=1)
        )
        db.add(jam)
        await db.commit()
        await db.refresh(jam)
        
        # Surveys
        # u2 votes to leave
        s2 = JamSurvey(jam_id=jam.id, user_id=u2.id, continue_in_team=False)
        # u1 (Lead) votes to avoid u3
        s1 = JamSurvey(jam_id=jam.id, user_id=u1.id, continue_in_team=True, avoid_member_id=u3.id)
        # u3 wants to stay
        s3 = JamSurvey(jam_id=jam.id, user_id=u3.id, continue_in_team=True)
        
        db.add_all([s1, s2, s3])
        await db.commit()
        
        print(f"Created Team ID: {team.id}, Jam ID: {jam.id}")

asyncio.run(setup())
