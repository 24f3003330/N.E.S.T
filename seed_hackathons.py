import asyncio
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import async_session
from app.models.hackathon import Hackathon, HackathonStatus
from app.models.user import User

async def seed_hackathons():
    async with async_session() as db:
        # Get any user to be the creator
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        
        if not user:
            print("No users found in the database. Please register a user first.")
            return

        print(f"Using user {user.full_name} (ID: {user.id}) as the creator.")

        now = datetime.now(timezone.utc)

        hackathons = [
            Hackathon(
                title="Global AI Challenge 2026",
                description="Build the next generation of LLM applications to solve real-world problems. Focus areas include healthcare, education, and climate tech.",
                organizer="OpenAI & Microsoft",
                created_by=user.id,
                start_date=now + timedelta(days=5),
                end_date=now + timedelta(days=7),
                registration_deadline=now + timedelta(days=3),
                max_team_size=4,
                min_team_size=2,
                required_capabilities_json=json.dumps(["Python", "Machine Learning", "React", "UI/UX Design"]),
                tags_json=json.dumps(["AI", "Healthcare", "Education"]),
                status=HackathonStatus.UPCOMING
            ),
            Hackathon(
                title="Smart Campus IoT Hack",
                description="Join us to make our university campus smarter, greener, and more connected using IoT devices and data analytics.",
                organizer="University Tech Board",
                created_by=user.id,
                start_date=now - timedelta(days=1),
                end_date=now + timedelta(days=1),
                registration_deadline=now - timedelta(days=2),
                max_team_size=5,
                min_team_size=3,
                required_capabilities_json=json.dumps(["C++", "Python", "Data Analysis", "Project Management"]),
                tags_json=json.dumps(["IoT", "Smart Campus", "Green Tech"]),
                status=HackathonStatus.ACTIVE
            ),
            Hackathon(
                title="FinTech Disruptors Buildathon",
                description="Redefine the future of finance. Build decentralized applications, payment gateways, and innovative banking solutions.",
                organizer="Stripe & Plaid",
                created_by=user.id,
                start_date=now - timedelta(days=10),
                end_date=now - timedelta(days=8),
                registration_deadline=now - timedelta(days=12),
                max_team_size=4,
                min_team_size=1,
                required_capabilities_json=json.dumps(["Solidity", "Node.js", "Financial Modeling", "Figma"]),
                tags_json=json.dumps(["FinTech", "Web3", "Blockchain"]),
                status=HackathonStatus.COMPLETED
            )
        ]

        for h in hackathons:
            db.add(h)
        
        await db.commit()
        print("Successfully seeded 3 mock hackathons (1 Upcoming, 1 Active, 1 Completed).")

if __name__ == "__main__":
    asyncio.run(seed_hackathons())
