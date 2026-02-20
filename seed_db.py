import asyncio
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.user import User, ArchetypeEnum
from app.models.hackathon import Hackathon
from app.models.team import Team
from app.models.chat_room import ChatRoom
from app.models.team_membership import TeamMembership
from app.models.team_invitation import TeamInvitation
from app.models.capability import Capability, CategoryEnum, ProficiencyEnum

async def async_main():
    engine = create_async_engine("sqlite+aiosqlite:///smartcampus.db")
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with async_session() as session:
        # Create users
        u1 = User(email="alice@example.com", full_name="Alice Builder", account_type="Leader", archetype=ArchetypeEnum.BUILDER, bio="I love building scalable backends.")
        u2 = User(email="bob@example.com", full_name="Bob Designer", account_type="Member", archetype=ArchetypeEnum.DESIGNER, bio="UI/UX enthusiast.")
        u3 = User(email="charlie@example.com", full_name="Charlie Research", account_type="Member", archetype=ArchetypeEnum.RESEARCHER, bio="Data science is my passion.")
        u4 = User(email="diana@example.com", full_name="Diana Communicator", account_type="Member", archetype=ArchetypeEnum.COMMUNICATOR, bio="I make sure ideas are heard.")
        u5 = User(email="eve@example.com", full_name="Eve Strategist", account_type="Member", archetype=ArchetypeEnum.STRATEGIST, bio="Planning the next big thing.")
        session.add_all([u1, u2, u3, u4, u5])
        await session.flush()
        
        # Add Capabilities
        caps = [
            Capability(name="Python", category=CategoryEnum.TECHNICAL, proficiency_level=ProficiencyEnum.EXPERT, user_id=u1.id),
            Capability(name="React", category=CategoryEnum.TECHNICAL, proficiency_level=ProficiencyEnum.ADVANCED, user_id=u1.id),
            
            Capability(name="Figma", category=CategoryEnum.DESIGN, proficiency_level=ProficiencyEnum.EXPERT, user_id=u2.id),
            Capability(name="React", category=CategoryEnum.TECHNICAL, proficiency_level=ProficiencyEnum.BEGINNER, user_id=u2.id),
            
            Capability(name="Machine Learning", category=CategoryEnum.TECHNICAL, proficiency_level=ProficiencyEnum.ADVANCED, user_id=u3.id),
            Capability(name="Python", category=CategoryEnum.TECHNICAL, proficiency_level=ProficiencyEnum.INTERMEDIATE, user_id=u3.id),

            Capability(name="Technical Writing", category=CategoryEnum.SOFT_SKILL, proficiency_level=ProficiencyEnum.EXPERT, user_id=u4.id),
            
            Capability(name="Project Management", category=CategoryEnum.DOMAIN, proficiency_level=ProficiencyEnum.ADVANCED, user_id=u5.id),
        ]
        session.add_all(caps)
        await session.flush()

        # Create hackathon with required capabilities
        req_caps = json.dumps(["Python", "React", "Machine Learning"])
        h = Hackathon(
            title="AI Innovation Hackathon", 
            description="Build the next gen AI tools.",
            created_by=u1.id, 
            status="Upcoming",
            required_capabilities_json=req_caps
        )
        session.add(h)
        await session.flush()
        
        # Create team
        t = Team(name="The Mavericks", description="Building an AI campus guide", lead_id=u1.id, hackathon_id=h.id, max_size=4, status="Forming")
        session.add(t)
        await session.flush()
        
        # Create membership
        tm = TeamMembership(team_id=t.id, user_id=u1.id, role="Lead")
        session.add(tm)
        
        # Create chat room
        cr = ChatRoom(team_id=t.id)
        session.add(cr)
        
        # Invite Bob
        inv = TeamInvitation(team_id=t.id, from_user_id=u1.id, to_user_id=u2.id, direction="Invite", status="Pending", message="We need your design skills!")
        session.add(inv)

        # Charlie forms their own team
        t2 = Team(name="Data Wizards", description="Predicting grades with ML", lead_id=u3.id, hackathon_id=h.id, max_size=3, status="Forming")
        session.add(t2)
        await session.flush()
        tm2 = TeamMembership(team_id=t2.id, user_id=u3.id, role="Lead")
        cr2 = ChatRoom(team_id=t2.id)
        session.add_all([tm2, cr2])
        
        await session.commit()
    print("Database seeded with rich matching data successfully.")

asyncio.run(async_main())
