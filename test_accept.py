import asyncio
from sqlalchemy import select, func
from app.database import async_session
from app.models.team_invitation import TeamInvitation, InvitationStatus
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.models.notification import Notification

async def main():
    async with async_session() as db:
        # Get an invite to test
        res = await db.execute(select(TeamInvitation).limit(1))
        inv = res.scalar_one_or_none()
        
        if not inv:
            print("No invites to test.")
            return
            
        print(f"Testing invite: {inv.id} for team {inv.team_id}")
        
        try:
            # 1. Fetch team
            team_res = await db.execute(select(Team).where(Team.id == inv.team_id))
            team = team_res.scalar_one_or_none()
            print(f"Team: {team.name}, object: {team}")
            
            # 2. Simulate Acceptance Math
            action = "accept"
            if action == "accept":
                inv.status = InvitationStatus.Accepted
                
                # Check direction properly
                inv_dir = getattr(inv.direction, 'value', inv.direction)
                new_member_id = inv.to_user_id if inv_dir == "Invite" else inv.from_user_id
                
                print(f"Calculated new member: {new_member_id} (From dir: {inv_dir})")
                
                # Mem check
                mem_check = await db.execute(
                    select(TeamMembership).where(
                        TeamMembership.team_id == inv.team_id,
                        TeamMembership.user_id == new_member_id,
                        TeamMembership.left_at.is_(None)
                    )
                )
                exists = mem_check.scalar_one_or_none()
                print(f"Membership check: {'Exists' if exists else 'Does not exist'}")
                
                if not exists:
                    # Size check
                    current_members_result = await db.execute(
                        select(func.count(TeamMembership.user_id)).where(
                            TeamMembership.team_id == inv.team_id,
                            TeamMembership.left_at.is_(None)
                        )
                    )
                    current_count = current_members_result.scalar() or 0
                    print(f"Current Team Count: {current_count}, Team max size: {team.max_size}")
                    
                    if team.max_size and current_count >= team.max_size:
                        print("FAILED: Team is full")
                    else:
                        print("SUCCESS: Ready to add member")
                        
            print("Finished simulation without throwing exception.")
        except Exception as e:
            import traceback
            print("EXCEPTION CAUGHT:")
            traceback.print_exc()

asyncio.run(main())
