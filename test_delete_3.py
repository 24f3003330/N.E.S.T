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
    try:
        async with async_session() as db:
            team_result = await db.execute(select(Team).where(Team.id == 3))
            team = team_result.scalar_one_or_none()
            if not team:
                print("Team 3 not found.")
                return

            print("Team found. Simulating cascade deletes...")
            
            chatrooms = await db.execute(select(ChatRoom).where(ChatRoom.team_id == team.id))
            for room in chatrooms.scalars().all():
                await db.execute(Message.__table__.delete().where(Message.room_id == room.id))
            await db.execute(ChatRoom.__table__.delete().where(ChatRoom.team_id == team.id))
            print("Chatrooms deleted.")
            
            await db.execute(TeamInvitation.__table__.delete().where(TeamInvitation.team_id == team.id))
            print("Invitations deleted.")
            await db.execute(JoinRequest.__table__.delete().where(JoinRequest.team_id == team.id))
            print("Requests deleted.")
            await db.execute(Rating.__table__.delete().where(Rating.team_id == team.id))
            print("Ratings deleted.")
            await db.execute(TeamMembership.__table__.delete().where(TeamMembership.team_id == team.id))
            print("Memberships deleted.")
            
            await db.delete(team)
            await db.commit()
            print("Successfully deleted!")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
