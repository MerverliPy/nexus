"""WebSocket router for real-time task updates."""

from fastapi import APIRouter, WebSocket, status
from sqlalchemy import select

from nexus.api.ws_manager import manager
from nexus.database import AsyncSessionLocal
from nexus.models.user import User
from nexus.utils.security import decode_token

router = APIRouter()


@router.websocket("/ws/tasks")
async def task_websocket(ws: WebSocket):
    """WebSocket endpoint for live task updates.

    Client must send an auth token as the first message:
    {"token": "<access_token>"}
    """
    await ws.accept()

    # Receive auth token
    try:
        token_msg = await ws.receive_json()
    except Exception:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    token = token_msg.get("token", "")
    payload = decode_token(token)

    if payload is None:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = payload.get("sub")
    if user_id is None:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Verify user exists and is active
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            await ws.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await manager.connect(user.id, ws)

        try:
            # Send confirmation
            await ws.send_json({"event": "connected", "data": {"user_id": user.id}})

            # Keep connection alive — listen for client close / ping
            while True:
                msg = await ws.receive_text()
                if msg == "ping":
                    await ws.send_json({"event": "pong"})
        except Exception:
            pass
        finally:
            manager.disconnect(user.id, ws)
