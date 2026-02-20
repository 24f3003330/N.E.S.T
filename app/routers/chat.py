"""
WebSocket Chat router — real-time team collaboration with built-in N.E.S.T bot.
"""

from typing import Dict, List, Optional
import sys
import os

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db, async_session
from app.models.capability import Capability
from app.models.user import User
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.models.chat_room import ChatRoom
from app.models.message import Message
from app.routers.auth import get_current_user
from app.services.matching import score_user_for_team

router = APIRouter(prefix="/chat", tags=["chat"])
templates = Jinja2Templates(directory="app/templates")

# ==============================================================================
# Connection Manager
# ==============================================================================

class ConnectionManager:
    def __init__(self):
        # Maps room_id (int) to a list of active WebSockets
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: int):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: int):
        if room_id in self.active_connections:
            if websocket in self.active_connections[room_id]:
                self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast(self, message: dict, room_id: int):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

manager = ConnectionManager()

# ==============================================================================
# HTTP Routes (UI and History)
# ==============================================================================

@router.get("/{room_id}", response_class=HTMLResponse)
async def get_chat_page(
    room_id: int, 
    request: Request, 
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Render the chat interface for a specific team's chat room."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    # Validate room exists
    res_room = await db.execute(select(ChatRoom).where(ChatRoom.id == room_id))
    room = res_room.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Chat room not found")

    # Validate the user is a member of the underlying team
    res_membership = await db.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == room.team_id,
            TeamMembership.user_id == current_user.id,
            TeamMembership.left_at == None
        )
    )
    membership = res_membership.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be a member of this team to access the chat.")

    # Fetch team
    res_team = await db.execute(select(Team).where(Team.id == room.team_id))
    team = res_team.scalar_one()

    # Fetch active members for the sidebar
    res_members = await db.execute(
        select(User)
        .join(TeamMembership, TeamMembership.user_id == User.id)
        .where(
            TeamMembership.team_id == room.team_id,
            TeamMembership.left_at == None
        )
    )
    members = list(res_members.scalars().all())

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "current_user": current_user,
            "room": room,
            "team": team,
            "members": members
        }
    )

@router.get("/{room_id}/history")
async def get_chat_history(
    room_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns the last 50 messages for the room."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    # Authorize
    res_room = await db.execute(select(ChatRoom).where(ChatRoom.id == room_id))
    room = res_room.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
        
    res_mem = await db.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == room.team_id,
            TeamMembership.user_id == current_user.id,
            TeamMembership.left_at == None
        )
    )
    if not res_mem.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a team member")

    # Fetch last 50 messages, ordered ascending by time (oldest first among the 50 newest)
    res_msgs = await db.execute(
        select(Message)
        .where(Message.chat_room_id == room_id)
        .order_by(desc(Message.created_at))
        .limit(50)
    )
    messages = list(res_msgs.scalars().all())
    messages.reverse()  # chronological order for UI display

    # Fetch sending user details to enrich the payload
    user_ids = {m.sender_id for m in messages if not m.is_bot}
    users = {}
    if user_ids:
        res_users = await db.execute(select(User).where(User.id.in_(user_ids)))
        users = {u.id: {"name": u.full_name, "avatar": u.avatar_url} for u in res_users.scalars()}

    history = []
    for m in messages:
        payload = {
            "id": m.id,
            "content": m.content,
            "timestamp": m.created_at.isoformat(),
            "is_bot": m.is_bot
        }
        if m.is_bot:
            payload["sender_name"] = "N.E.S.T Bot"
            payload["sender_id"] = 0
        else:
            payload["sender_name"] = users.get(m.sender_id, {}).get("name", "Unknown User")
            payload["sender_id"] = m.sender_id
            
        history.append(payload)

    return {"messages": history}

# ==============================================================================
# WebSocket Endpoint + Bot Logic
# ==============================================================================

async def process_bot_command(command_text: str, room_id: int, team_id: int) -> str:
    """Evaluate a /bot command and return the markdown/text response string."""
    cmd = command_text[4:].strip().lower() # remove "/bot"
    
    if cmd == "help" or cmd == "":
        return (
            "**🤖 N.E.S.T Bot Commands:**<br>"
            "👉 `/bot help` - Show this menu<br>"
            "👉 `/bot suggest` - View current team compatibility gaps<br>"
            "👉 `/bot github` - Get the team's repository link<br>"
            "👉 `/bot members` - List all members and their capabilities"
        )
    
    async with async_session() as db:
        res_members = await db.execute(
            select(User)
            .options(selectinload(User.capabilities))
            .join(TeamMembership, TeamMembership.user_id == User.id)
            .where(
                TeamMembership.team_id == team_id,
                TeamMembership.left_at == None
            )
        )
        active_mems = list(res_members.scalars().all())
        
        # We also need the user's role to format the chat bot output
        res_roles = await db.execute(
            select(TeamMembership.user_id, TeamMembership.role)
            .where(
                TeamMembership.team_id == team_id,
                TeamMembership.left_at == None
            )
        )
        roles = {row[0]: row[1] for row in res_roles.all()}

        res_team = await db.execute(select(Team).where(Team.id == team_id))
        team = res_team.scalar_one_or_none()
        if not team:
            return "❌ Error: Could not locate team data."

        if cmd == "github":
            repo = team.github_repo_url
            if repo:
                return f"**🐙 GitHub Repo:** <a href='{repo}' target='_blank'>{repo}</a>"
            return "This team hasn't linked a GitHub repository yet!"
            
        elif cmd == "members":
            response = f"**👨‍💻 Active Members ({len(active_mems)}/{team.max_size or '∞'}):**<br>"
            for user in active_mems:
                role = roles.get(user.id, "Member")
                caps = [c.name for c in user.capabilities]
                cap_str = ", ".join(caps) if caps else "No specific capabilities listed"
                response += f"- **{user.full_name}** ({role.value if hasattr(role, 'value') else role}): <i>{cap_str}</i><br>"
            return response
            
        elif cmd == "suggest":
            # Just calculating an arbitrary "Team Completeness Data Map" based on required roles, 
            # or listing what archetypes are missing. For simplicity, we just list the vibe composition.
            active_users = active_mems
            archetypes_present = {getattr(u.archetype, 'value', u.archetype) for u in active_users if u.archetype}
            
            all_archetypes = {"Builder", "Designer", "Researcher", "Communicator", "Strategist"}
            missing = all_archetypes - archetypes_present
            
            response = "**🧩 Team Chemistry Status:**<br>"
            response += f"Present: {', '.join(archetypes_present) or 'None'}<br>"
            if missing:
                response += f"💡 *Suggestion:* You look like you're missing a **{list(missing)[0]}**. Time to recruit!"
            else:
                response += "🔥 Your team has a perfect blend of all 5 archetypes! Unstoppable."
            return response
            
        else:
            return f"I don't understand the command `{cmd}`. Try `/bot help`."


@router.websocket("/ws/{room_id}")
async def websocket_chat_endpoint(websocket: WebSocket, room_id: int, user_id: int):
    """
    WebSocket endpoint for actual chat streaming.
    (Note: In a true production app, auth is extracted from query params/cookies during handshake)
    """
    # Accept connection
    await manager.connect(websocket, room_id)
    
    # Simple handshake verification
    try:
        async with async_session() as db:
            room_res = await db.execute(select(ChatRoom).where(ChatRoom.id == room_id))
            room = room_res.scalar_one_or_none()
            if not room:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
                
            mem_res = await db.execute(
                select(TeamMembership).where(
                    TeamMembership.team_id == room.team_id,
                    TeamMembership.user_id == user_id,
                    TeamMembership.left_at == None
                )
            )
            membership = mem_res.scalar_one_or_none()
            if not membership:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            
            user_res = await db.execute(select(User).where(User.id == user_id))
            user = user_res.scalar_one()

            team_id = room.team_id
            
        # Broadcast user joining (Optional, keeping it clean for now)
        # await manager.broadcast({"content": f"{user.full_name} joined the chat", "is_bot": True}, room_id)

        # Receive loop
        while True:
            data = await websocket.receive_text()
            
            # Save the user's message
            async with async_session() as db:
                user_msg = Message(
                    chat_room_id=room_id,
                    sender_id=user_id,
                    content=data,
                    is_bot=False
                )
                db.add(user_msg)
                await db.commit()
                await db.refresh(user_msg)
                
            # Broadcast the human message
            await manager.broadcast({
                "id": user_msg.id,
                "content": user_msg.content,
                "timestamp": user_msg.created_at.isoformat(),
                "sender_id": user_id,
                "sender_name": user.full_name,
                "is_bot": False
            }, room_id)
            
            # Bot Hook Execution
            if data.startswith("/bot"):
                bot_response_text = await process_bot_command(data, room_id, team_id)
                # Save bot message
                async with async_session() as db:
                    bot_msg = Message(
                        chat_room_id=room_id,
                        sender_id=user_id, # Can technically map to system, but keeping it simple
                        content=bot_response_text,
                        is_bot=True
                    )
                    db.add(bot_msg)
                    await db.commit()
                    await db.refresh(bot_msg)
                    
                # Broadcast bot message
                await manager.broadcast({
                    "id": bot_msg.id,
                    "content": bot_msg.content,
                    "timestamp": bot_msg.created_at.isoformat(),
                    "sender_id": 0,
                    "sender_name": "N.E.S.T Bot",
                    "is_bot": True
                }, room_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
        # print(f"Client {user_id} disconnected from room {room_id}")
