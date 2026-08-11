import asyncio
import json
import websockets

clients = {}

# Stores messages/events for the CURRENT room
message_history = []

MAX_HISTORY = 100

# Temporary disconnects used to recognize refreshes
pending_disconnects = {}

RECONNECT_DELAY = 5


async def broadcast(message, exclude=None):
    """Send a message to all connected users except exclude."""
    recipients = [
        client for client in clients
        if client != exclude
    ]

    if recipients:
        await asyncio.gather(
            *(client.send(message) for client in recipients),
            return_exceptions=True
        )


async def send_user_list():
    users = list(clients.values())

    await broadcast(json.dumps({
        "type": "users",
        "count": len(users),
        "users": users
    }))


def add_to_history(event):
    message_history.append(event)

    if len(message_history) > MAX_HISTORY:
        message_history.pop(0)


async def handle_disconnect(username):

    try:
        await asyncio.sleep(RECONNECT_DELAY)

        # User refreshed and reconnected
        if username in pending_disconnects:

            del pending_disconnects[username]

            if username in clients.values():
                return

            # User actually disconnected
            print(f"{username} disconnected")

            event = {
                "type": "system",
                "message": f"{username} disconnected"
            }

            add_to_history(event)

            await broadcast(json.dumps(event))

        # Room is empty
        if len(clients) == 0:

            message_history.clear()

            print("Room empty - chat history cleared")

    except asyncio.CancelledError:
        pass


async def handler(websocket):

    username = None
    explicit_leave = False

    try:

        # --------------------------------
        # RECEIVE USERNAME
        # --------------------------------

        data = await websocket.recv()

        info = json.loads(data)

        username = info["username"]

        # --------------------------------
        # CHECK FOR REFRESH / RECONNECT
        # --------------------------------

        reconnecting = username in pending_disconnects

        if reconnecting:

            task = pending_disconnects.pop(username)

            task.cancel()

            print(f"{username} reconnected")

        # --------------------------------
        # ADD CLIENT
        # --------------------------------

        clients[websocket] = username

        print(f"{username} connected")

        # --------------------------------
        # REFRESH / RECONNECT
        # --------------------------------

        if reconnecting:

            # Only a reconnecting user gets
            # the existing conversation.
            await websocket.send(json.dumps({
                "type": "history",
                "messages": message_history
            }))

        # --------------------------------
        # BRAND NEW USER
        # --------------------------------

        else:

            # NEW USER DOES NOT GET OLD CHAT

            # Tell ONLY the existing users
            # that someone joined.

            event = {
                "type": "system",
                "message": f"{username} joined the chat"
            }

            add_to_history(event)

            await broadcast(
                json.dumps(event),
                exclude=websocket
            )

        # --------------------------------
        # UPDATE USER LIST
        # --------------------------------

        await send_user_list()

        # --------------------------------
        # RECEIVE MESSAGES
        # --------------------------------

        async for message in websocket:

            data = json.loads(message)

            # ==============================
            # NORMAL MESSAGE
            # ==============================

            if data["type"] == "message":

                chat_message = {
                    "type": "message",
                    "username": username,
                    "message": data["message"]
                }

                add_to_history(chat_message)

                await broadcast(
                    json.dumps(chat_message)
                )

            # ==============================
            # EXPLICIT LEAVE
            # ==============================

            elif data["type"] == "leave":

                explicit_leave = True

                if websocket in clients:
                    del clients[websocket]

                print(f"{username} left the chat")

                event = {
                    "type": "system",
                    "message": f"{username} left the chat"
                }

                add_to_history(event)

                await broadcast(
                    json.dumps(event)
                )

                await send_user_list()

                # If nobody is left,
                # completely clear the room.

                if len(clients) == 0:

                    message_history.clear()

                    print("Room empty - chat history cleared")

                break

    except websockets.exceptions.ConnectionClosed:
        pass

    finally:

        # Browser refresh / browser close /
        # network disconnect

        if websocket in clients:

            del clients[websocket]

            if not explicit_leave:

                task = asyncio.create_task(
                    handle_disconnect(username)
                )

                pending_disconnects[username] = task

            await send_user_list()


async def main():

    server = await websockets.serve(
        handler,
        "0.0.0.0",
        8765
    )

    print("=================================")
    print("        GROUP CHAT SERVER")
    print("=================================")
    print("Server running on port 8765")
    print("Waiting for users...")
    print("Refresh-safe reconnection enabled")
    print("New users start with a fresh view")
    print("Press Ctrl+C to stop")

    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
