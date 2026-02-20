import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from app.database import async_session
from app.models.user import User
from app.models.idea_jam import IdeaJam, JamStatus
from app.models.idea_jam_entry import IdeaJamEntry

async def setup():
    async with async_session() as db:
        users = (await db.execute(select(User).limit(2))).scalars().all()
        u1, u2 = users[0], users[1]
        
        jam = IdeaJam(
            team_id=1,
            started_by=u1.id,
            status=JamStatus.Completed,
            ends_at=datetime.utcnow() - timedelta(minutes=1)
        )
        db.add(jam)
        await db.commit()
        await db.refresh(jam)
        
        e1 = IdeaJamEntry(jam_id=jam.id, user_id=u1.id, idea_text="Test idea 1", votes=5)
        e2 = IdeaJamEntry(jam_id=jam.id, user_id=u2.id, idea_text="Test idea 2", votes=2)
        db.add_all([e1, e2])
        await db.commit()
        
        print(f"Created completed Jam with ID: {jam.id}")

asyncio.run(setup())
