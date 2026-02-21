import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models.notification import Notification

async def main():
    async with async_session() as db:
        print("Testing Notification insertion")
        try:
            notif = Notification(
                user_id=1,
                message="✅ Test accepted your request",
                link="/teams/1"
            )
            db.add(notif)
            await db.commit()
            print("Successfully added notification.")
        except Exception as e:
            print(f"Exception during insert: {e}")

asyncio.run(main())
