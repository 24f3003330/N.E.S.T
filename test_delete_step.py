import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models.team import Team
from app.models.message import Message
from app.models.chat_room import ChatRoom
from app.models.team_invitation import TeamInvitation
from app.models.team_membership import TeamMembership
from app.models.request import JoinRequest
from app.models.rating import Rating

async def main():
    async with async_session() as db:
        team_id = 3
        print("Starting step-by-step deletion for team", team_id)
        
        chatrooms = await db.execute(select(ChatRoom).where(ChatRoom.team_id == team_id))
        for room in chatrooms.scalars().all():
            print(f"Deleting messages for room {room.id}")
            await db.execute(Message.__table__.delete().where(Message.room_id == room.id))
            
        print("Deleting ChatRooms")
        await db.execute(ChatRoom.__table__.delete().where(ChatRoom.team_id == team_id))
        
        print("Deleting TeamInvitations")
        await db.execute(TeamInvitation.__table__.delete().where(TeamInvitation.team_id == team_id))
        
        print("Deleting JoinRequests")
        await db.execute(JoinRequest.__table__.delete().where(JoinRequest.team_id == team_id))
        
        print("Deleting Ratings")
        await db.execute(Rating.__table__.delete().where(Rating.team_id == team_id))
        
        print("Deleting TeamMemberships")
        await db.execute(TeamMembership.__table__.delete().where(TeamMembership.team_id == team_id))
        
        team_result = await db.execute(select(Team).where(Team.id == team_id))
        team = team_result.scalar_one_or_none()
        if team:
            print("Deleting Team")
            await db.delete(team)
            
        try:
            print("Committing transaction...")
            await db.commit()
            print("Success!")
        except Exception as e:
            print("Error during commit:", type(e).__name__)
            print(e)
            
asyncio.run(main())
