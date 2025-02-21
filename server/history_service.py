import os
import asyncio
import aioredis
import redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

app = FastAPI()

# Path to store chat history files
CHAT_HISTORY_DIR = "chat_history"
os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)

# Connect to Redis (Local Docker)
REDIS_HOST = "localhost"
REDIS_PORT = 6379
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


# Async Redis connection for WebSocket Pub/Sub
async def get_redis():
    return await aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)


# WebSocket connections per room
active_connections = {}


# ====== REST API ======
class ChatRoom(BaseModel):
    chat_room: str


@app.get("/chat-history")
def get_chat_history(chat_room: str):
    """Returns chat history of a specified chat-room from a file."""
    file_path = os.path.join(CHAT_HISTORY_DIR, f"{chat_room}.txt")
    if not os.path.exists(file_path):
        return {"message": "No history found"}

    with open(file_path, "r") as f:
        history = f.readlines()

    return {"chat_room": chat_room, "history": history}


@app.post("/chat-history")
def create_chat_room(chat_room: str):
    """Creates a new file to store chat history for a chat-room."""
    file_path = os.path.join(CHAT_HISTORY_DIR, f"{chat_room}.txt")
    if os.path.exists(file_path):
        return {"message": "Chat room already exists"}

    open(file_path, "w").close()
    return {"message": f"Chat room '{chat_room}' created"}


# ====== WebSocket Communication ======
@app.websocket("/ws/{chat_room}")
async def websocket_endpoint(websocket: WebSocket, chat_room: str):
    """Handles WebSocket connections and broadcasts messages using Redis."""
    await websocket.accept()

    # Store connection
    if chat_room not in active_connections:
        active_connections[chat_room] = []
    active_connections[chat_room].append(websocket)

    # Redis Subscription Task
    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(chat_room)

    async def listen_to_redis():
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])

    redis_task = asyncio.create_task(listen_to_redis())

    try:
        while True:
            data = await websocket.receive_text()

            # Save to file
            file_path = os.path.join(CHAT_HISTORY_DIR, f"{chat_room}.txt")
            with open(file_path, "a") as f:
                f.write(data + "\n")

            # Publish to Redis (other pods will receive it)
            redis_client.publish(chat_room, data)

    except WebSocketDisconnect:
        active_connections[chat_room].remove(websocket)
        await pubsub.unsubscribe(chat_room)
        redis_task.cancel()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
