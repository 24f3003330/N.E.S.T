"""Notifications router — fetch, read, and mark-all-read."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select, update, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def get_notifications(
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return last 20 notifications + unread count for the current user."""
    if not current_user:
        return JSONResponse({"notifications": [], "unread_count": 0})

    # Unread count
    count_result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    )
    unread_count = count_result.scalar() or 0

    # Last 20 notifications
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(desc(Notification.created_at))
        .limit(20)
    )
    notifs = result.scalars().all()

    return {
        "unread_count": unread_count,
        "notifications": [
            {
                "id": n.id,
                "message": n.message,
                "link": n.link or "#",
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else "",
            }
            for n in notifs
        ],
    }


@router.post("/read/{notif_id}")
async def mark_read(
    notif_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a single notification as read and redirect to its link."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    result = await db.execute(
        select(Notification).where(
            Notification.id == notif_id,
            Notification.user_id == current_user.id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = True
    await db.commit()

    return RedirectResponse(url=notif.link or "/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/read-all")
async def mark_all_read(
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    if not current_user:
        return JSONResponse({"ok": False})

    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
        .values(is_read=True)
    )
    await db.commit()
    return JSONResponse({"ok": True})
