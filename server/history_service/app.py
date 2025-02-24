import os
import asyncio
import redis.asyncio as redis
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from fastapi.middleware.cors import CORSMiddleware

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

# Allow cross-origin requests (adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path to store chat history files
CHAT_HISTORY_DIR = "chat_history"
os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)

# Redis connection settings
REDIS_HOST = "localhost"
REDIS_PORT = 6379

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Store active WebSocket connections and their Redis listener task per chat room.
# Structure: { chat_room_name: { "clients": [WebSocket, ...], "redis_task": asyncio.Task } }
active_connections: Dict[str, Dict[str, Optional[object]]] = {}

# ====== REST API ======

class ChatRoomRequest(BaseModel):
    username: str
    chat_room_name: str

@app.post("/create-chat-room")
async def create_chat_room(request: ChatRoomRequest):
    """Creates a new chat room and broadcasts an event message."""
    chat_room_name = request.chat_room_name
    username = request.username

    file_path = os.path.join(CHAT_HISTORY_DIR, f"{chat_room_name}.txt")

    if os.path.exists(file_path):
        logger.warning(f"Chat room '{chat_room_name}' already exists.")
        return {"message": "Chat room already exists"}

    # Create empty file for chat history
    open(file_path, "w").close()
    logger.info(f"Chat room '{chat_room_name}' created.")

    # Broadcast room creation message
    event_message = f"🟢 {username} created the room '{chat_room_name}'"
    await save_and_broadcast_message(chat_room_name, event_message)

    websocket_url = f"ws://localhost:5000/ws/{chat_room_name}"
    return {"chat_room": chat_room_name, "websocket_url": websocket_url}

@app.post("/join-chat-room")
async def join_chat_room(request: ChatRoomRequest):
    """A user joins an existing chat room, receives history, and triggers a broadcast event."""
    chat_room_name = request.chat_room_name
    username = request.username

    file_path = os.path.join(CHAT_HISTORY_DIR, f"{chat_room_name}.txt")

    if not os.path.exists(file_path):
        logger.warning(f"Chat room '{chat_room_name}' does not exist.")
        raise HTTPException(status_code=404, detail="Chat room not found")

    # Read chat history
    with open(file_path, "r", encoding="utf-8") as f:
        history = [line.strip() for line in f.readlines()]

    # Broadcast join message
    event_message = f"🔵 {username} joined the chat"
    await save_and_broadcast_message(chat_room_name, event_message)

    websocket_url = f"ws://localhost:5000/ws/{chat_room_name}"
    return {"chat_room": chat_room_name, "history": history, "websocket_url": websocket_url}

# ====== WebSocket Communication ======

@app.websocket("/ws/{chat_room_name}")
async def websocket_endpoint(websocket: WebSocket, chat_room_name: str):
    """Handles WebSocket connections and broadcasts messages using a shared Redis listener per chat room."""
    await websocket.accept()
    logger.info(f"WebSocket connected for room: {chat_room_name}")

    # Initialize data for the room if needed
    if chat_room_name not in active_connections:
        active_connections[chat_room_name] = {"clients": [], "redis_task": None}
    active_connections[chat_room_name]["clients"].append(websocket)

    # If no Redis listener is running for this room, start one.
    if active_connections[chat_room_name]["redis_task"] is None:
        active_connections[chat_room_name]["redis_task"] = asyncio.create_task(listen_to_redis(chat_room_name))

    try:
        while True:
            data = await websocket.receive_json()
            username = data.get("username")
            message_content = data.get("message")

            if not username or not message_content:
                await websocket.send_text("❌ Invalid message format. Use {'username': '<name>', 'message': '<text>'}")
                continue

            full_message = f"{username}: {message_content}"
            await save_and_broadcast_message(chat_room_name, full_message)

    except WebSocketDisconnect:
        logger.warning(f"WebSocket disconnected for room: {chat_room_name}")
        active_connections[chat_room_name]["clients"].remove(websocket)
        # If no clients remain, cancel the Redis listener and clean up.
        if not active_connections[chat_room_name]["clients"]:
            redis_task = active_connections[chat_room_name]["redis_task"]
            if redis_task:
                redis_task.cancel()
            del active_connections[chat_room_name]
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()

async def listen_to_redis(chat_room_name: str):
    """Listens for new messages from Redis for a specific chat room and broadcasts them to all clients."""
    redis_client_async = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    pubsub = redis_client_async.pubsub()
    await pubsub.subscribe(chat_room_name)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                logger.info(f"New message in {chat_room_name}: {message['data']}")
                # Broadcast to all clients in the room
                for ws in active_connections.get(chat_room_name, {}).get("clients", []):
                    try:
                        await ws.send_text(message["data"])
                    except Exception as e:
                        logger.error(f"Failed to send message to a client: {e}")
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(chat_room_name)
        await redis_client_async.aclose()

async def save_and_broadcast_message(chat_room_name: str, message: str):
    """Save a message to file and broadcast it via Redis."""
    file_path = os.path.join(CHAT_HISTORY_DIR, f"{chat_room_name}.txt")

    # Save to file
    try:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(message + "\n")
        logger.info(f"Message saved to {file_path}")
    except Exception as e:
        logger.error(f"Error writing to file {file_path}: {e}")

    # Publish to Redis
    try:
        await redis_client.publish(chat_room_name, message)
        logger.info(f"Message published to Redis channel {chat_room_name}: {message}")
    except Exception as e:
        logger.error(f"Error publishing to Redis: {e}")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI server on http://0.0.0.0:5000")
    uvicorn.run(app, host="0.0.0.0", port=5000)
