import asyncio
import websockets
import json
import pika

HOST = "localhost"
PORT = 8766  # WebSocket Port
RABBITMQ_HOST = "localhost"

# Active users and rooms
clients = {}  # username -> WebSocket
rooms = {"global": set()}  # room_name -> set of usernames


async def broadcast(room, message):
    """Send a message to all users in a room."""
    if room in rooms:
        for user in rooms[room]:
            if user in clients:
                try:
                    await clients[user].send(json.dumps({"room": room, "message": message}))
                except:
                    pass


async def handle_chat(websocket, path):
    """Handle chat messages."""
    username = None
    try:
        data = await websocket.recv()
        request = json.loads(data)
        username = request.get("username")

        if not username:
            await websocket.send(json.dumps({"status": "error", "message": "Invalid username"}))
            return

        clients[username] = websocket
        rooms["global"].add(username)

        await websocket.send(json.dumps({"status": "ok", "message": "Connected to chat!"}))

        while True:
            data = await websocket.recv()
            message = json.loads(data)
            command = message.get("command")

            if command == "message":
                content = message.get("content", "")
                room = message.get("room", "global")

                if username not in rooms.get(room, set()):
                    await websocket.send(json.dumps({"status": "error", "message": "You are not in this room"}))
                    continue

                chat_msg = f"{username}: {content}"
                await broadcast(room, chat_msg)

                # Send message to RabbitMQ for History Service
                connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
                channel = connection.channel()
                channel.queue_declare(queue="chat_history")
                channel.basic_publish(exchange="", routing_key="chat_history", body=json.dumps({"room": room, "message": chat_msg}))
                connection.close()

            elif command == "create_room":
                room = message.get("room")
                if room:
                    rooms[room] = {username}
                    await websocket.send(json.dumps({"status": "ok", "message": f"Room {room} created."}))

            elif command == "join_room":
                room = message.get("room")
                if room in rooms:
                    rooms[room].add(username)
                    await websocket.send(json.dumps({"status": "ok", "message": f"Joined room {room}"}))
                else:
                    await websocket.send(json.dumps({"status": "error", "message": "Room not found"}))
    except:
        pass
    finally:
        if username in clients:
            del clients[username]

start_server = websockets.serve(handle_chat, HOST, PORT)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
