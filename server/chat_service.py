from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
import logging
import pika
import threading
import requests
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# RabbitMQ configuration
RABBITMQ_HOST = "localhost"
AUTH_QUEUE = "auth_queue"
HISTORY_QUEUE = "chat_history_queue"

# Global state
# A set to store registered usernames
registered_users = set()
# Rooms: mapping room name -> set of WebSocket connections.
rooms = {"global": set()}

# --------------------------
# RabbitMQ functions for Chat Service
# --------------------------

def publish_to_history(message_data: dict):
    """
    Publishes a chat message to the history service via RabbitMQ.
    """
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue=HISTORY_QUEUE, durable=True)
        message_json = json.dumps(message_data)
        channel.basic_publish(exchange="", routing_key=HISTORY_QUEUE, body=message_json)
        connection.close()
        logger.info(f"Published message to history queue: {message_json}")
    except Exception as e:
        logger.error(f"Error publishing message to history: {e}")

def auth_callback(ch, method, properties, body):
    """
    Callback for messages from the auth_queue.
    Expected payload: {"username": "<username>"}
    """
    try:
        message_data = json.loads(body.decode("utf-8"))
        username = message_data.get("username")
        if username:
            registered_users.add(username)
            logger.info(f"Registered new user from auth: '{username}' added to global chat")
            # Broadcast to the global room that a new user has joined.
            broadcast_global({"command": "user_joined", "username": username})
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing auth message: {e}")

def start_auth_consumer():
    """
    Starts a RabbitMQ consumer for the auth_queue.
    """
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue=AUTH_QUEUE, durable=True)
        channel.basic_consume(queue=AUTH_QUEUE, on_message_callback=auth_callback)
        logger.info(f"Started auth consumer on queue '{AUTH_QUEUE}'.")
        channel.start_consuming()
    except Exception as e:
        logger.error(f"Auth consumer error: {e}")

def broadcast_global(message: dict):
    """
    Broadcast a message to all connected WebSocket clients in the global room.
    """
    for connection in list(rooms.get("global", set())):
        try:
            # Since we're in a non-async function, we can schedule sending on the connection's loop.
            # Here, we assume the websocket connection supports send_json() when awaited.
            # In production, you might need to use asyncio.create_task().
            import asyncio
            asyncio.create_task(connection.send_json(message))
        except Exception as e:
            logger.error(f"Error broadcasting global message: {e}")

# Start the auth consumer in a background thread on startup.
@app.on_event("startup")
def on_startup():
    threading.Thread(target=start_auth_consumer, daemon=True).start()
    # Ensure the global room exists.
    if "global" not in rooms:
        rooms["global"] = set()

# --------------------------
# HTTP helper to fetch room chat history
# --------------------------
def fetch_chat_history(room: str):
    """
    Fetch chat history for a room from the history service.
    Assumes history_service is running at http://127.0.0.1:8001.
    """
    try:
        response = requests.get("http://127.0.0.1:8001/history", params={"room": room})
        if response.status_code == 200:
            return response.json().get("messages", [])
        else:
            logger.error(f"Failed to fetch chat history for room '{room}': {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error fetching chat history: {e}")
        return []

# --------------------------
# WebSocket endpoint for Chat Service
# --------------------------
@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()
    logger.info(f"WebSocket connected: {username}")

    # Add user to registered_users if not already there.
    if username not in registered_users:
        registered_users.add(username)
        # Optionally broadcast to global room.
        broadcast_global({"command": "user_joined", "username": username})

    # Default room for new connections is "global"
    current_room = "global"
    if current_room not in rooms:
        rooms[current_room] = set()
    rooms[current_room].add(websocket)
    # Send chat history for the current room upon joining.
    history = fetch_chat_history(current_room)
    await websocket.send_json({"command": "history", "room": current_room, "messages": history})

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except Exception as e:
                logger.error("Invalid JSON received")
                continue

            command = message.get("command")
            if command == "message":
                # Send a chat message in the current room.
                content = message.get("content")
                if content:
                    msg_data = {
                        "room": current_room,
                        "username": username,
                        "message": content
                    }
                    # Broadcast the message to all connections in the current room.
                    for connection in list(rooms.get(current_room, set())):
                        try:
                            await connection.send_json({"command": "message", **msg_data})
                        except Exception as e:
                            logger.error(f"Error sending message: {e}")
                    # Publish the message to the history service via RabbitMQ.
                    publish_to_history(msg_data)
            elif command == "create_room":
                # Create a new chat room.
                room = message.get("room")
                if room:
                    if room in rooms:
                        await websocket.send_json({"error": f"Room '{room}' already exists."})
                    else:
                        rooms[room] = set()
                        await websocket.send_json({"command": "room_created", "room": room})
                        logger.info(f"Room created: {room}")
                else:
                    await websocket.send_json({"error": "Room name not provided."})
            elif command == "join_room":
                # Join an existing chat room.
                room = message.get("room")
                if room:
                    # Remove connection from current room.
                    if current_room in rooms and websocket in rooms[current_room]:
                        rooms[current_room].remove(websocket)
                    current_room = room
                    if room not in rooms:
                        # If the room doesn't exist, create it.
                        rooms[room] = set()
                    rooms[room].add(websocket)
                    # Fetch chat history for the room.
                    history = fetch_chat_history(room)
                    await websocket.send_json({"command": "history", "room": room, "messages": history})
                    logger.info(f"User '{username}' joined room '{room}'.")
                else:
                    await websocket.send_json({"error": "Room name not provided."})
            else:
                await websocket.send_json({"error": "Invalid command."})
    except WebSocketDisconnect:
        logger.info(f"User {username} disconnected")
        # Remove the websocket from all rooms.
        for room in rooms.values():
            if websocket in room:
                room.remove(websocket)
    except Exception as e:
        logger.error(f"Error in websocket connection: {e}")

if __name__ == "__main__":
    uvicorn.run("chat_service:app", host="127.0.0.1", port=8002, reload=True)
