import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Group Chat Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
#  In-memory state
#  clients: session_token → {websocket, username}
# ─────────────────────────────────────────────
clients: Dict[str, dict] = {}
message_history: list = []
MAX_HISTORY = 100


def utc_now() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

async def _send(ws: WebSocket, payload: dict):
    """Fire-and-forget send to a single socket."""
    try:
        await ws.send_text(json.dumps(payload))
    except Exception:
        pass


async def broadcast(payload: dict, exclude_token: Optional[str] = None):
    """Send to all connected clients, optionally excluding one session."""
    snapshot = list(clients.items())
    await asyncio.gather(
        *(
            _send(info["websocket"], payload)
            for token, info in snapshot
            if token != exclude_token
        ),
        return_exceptions=True,
    )


async def broadcast_all(payload: dict):
    """Send to every connected client."""
    await broadcast(payload, exclude_token=None)


async def push_user_list():
    """Broadcast the current online-user list to all clients."""
    users = [info["username"] for info in clients.values()]
    await broadcast_all({"type": "users", "count": len(users), "users": users})


def add_to_history(event: dict):
    message_history.append(event)
    if len(message_history) > MAX_HISTORY:
        message_history.pop(0)


def _clear_room():
    message_history.clear()
    print("[i] Room empty — history cleared")


# ─────────────────────────────────────────────
#  WebSocket endpoint
# ─────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    session_token: Optional[str] = None
    username: Optional[str] = None

    try:
        # ── 1. Receive join handshake ──────────────────────────────
        raw = await websocket.receive_text()
        data = json.loads(raw)

        if data.get("type") != "join":
            await websocket.close(code=1008)
            return

        session_token = (data.get("session_token") or "").strip()
        username = (data.get("username") or "").strip()

        if not session_token or not username:
            await websocket.close(code=1008)
            return

        # ── 2. Deduplicate same-browser tabs ───────────────────────
        #   If this session_token already has an active connection
        #   (another tab), close the old one silently and take over.
        if session_token in clients:
            old_ws = clients[session_token]["websocket"]
            try:
                await old_ws.send_text(json.dumps({
                    "type": "replaced",
                    "message": "You opened this chat in another tab. This tab is now active."
                }))
                await old_ws.close(code=4000)
            except Exception:
                pass

        # ── 3. Register client ─────────────────────────────────────
        clients[session_token] = {"websocket": websocket, "username": username}
        print(f"[+] {username} connected  (token …{session_token[-8:]})")

        # ── 4. Confirm join — NO history sent (Requirement 1) ──────
        await _send(websocket, {"type": "joined", "username": username})

        # Broadcast join event to everyone else
        join_event = {
            "type": "system",
            "message": f"{username} joined the chat",
            "timestamp": utc_now(),
        }
        add_to_history(join_event)
        await broadcast(join_event, exclude_token=session_token)

        # Push fresh user list to all
        await push_user_list()

        # ── 5. Message loop ────────────────────────────────────────
        async for raw_msg in websocket.iter_text():
            data = json.loads(raw_msg)
            msg_type = data.get("type")

            if msg_type == "message":
                chat_msg = {
                    "type": "message",
                    "username": username,
                    "message": data.get("message", ""),
                    "timestamp": utc_now(),
                }
                add_to_history(chat_msg)
                await broadcast_all(chat_msg)

            elif msg_type == "leave":
                # Explicit leave — remove immediately
                if session_token in clients and clients[session_token]["websocket"] is websocket:
                    del clients[session_token]

                leave_event = {
                    "type": "system",
                    "message": f"{username} left the chat",
                    "timestamp": utc_now(),
                }
                add_to_history(leave_event)
                await broadcast_all(leave_event)
                await push_user_list()

                if not clients:
                    _clear_room()

                break  # exit loop, finally will not re-broadcast

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"[!] Unexpected error: {exc}")

    finally:
        # ── 6. Clean up on disconnect ──────────────────────────────
        #   Only remove + notify if this websocket is still the active
        #   one for its session (not already replaced by another tab).
        if (
            session_token
            and session_token in clients
            and clients[session_token]["websocket"] is websocket
        ):
            del clients[session_token]
            print(f"[-] {username} disconnected  (token …{session_token[-8:]})")

            disconnect_event = {
                "type": "system",
                "message": f"{username} disconnected",
                "timestamp": utc_now(),
            }
            add_to_history(disconnect_event)

            try:
                await broadcast_all(disconnect_event)
                await push_user_list()
            except Exception:
                pass

            if not clients:
                _clear_room()
