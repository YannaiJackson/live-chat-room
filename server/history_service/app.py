import os
import asyncio
import redis.asyncio as redis
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, List


# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

# Path to store chat history files
CHAT_HISTORY_DIR = "chat_history"
os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)

# Connect to Redis (Local Docker)
REDIS_HOST = "localhost"
REDIS_PORT = 6379

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    logger.info("Connected to Redis successfully.")
except Exception as e:
    logger.error(f"Error connecting to Redis: {e}")
    raise

# Store active WebSocket connections per chat room
active_connections: Dict[str, List[WebSocket]] = {}


# ====== REST API ======
class ChatRoom(BaseModel):
    chat_room_name: str


@app.post("/create-chat-room")
def create_chat_room(chat_room_name: ChatRoom):
    """Creates a new file in the chat_history directory to store chat history for a chat-room."""
    try:
        chat_room_name = chat_room_name.chat_room_name
        file_path = os.path.join(CHAT_HISTORY_DIR, f"{chat_room_name}.txt")
        if os.path.exists(file_path):
            logger.warning(f"Chat room '{chat_room_name}' already exists.")
            return {"message": "Chat room already exists"}

        open(file_path, "w").close()
        logger.info(f"Chat room '{chat_room_name}' created.")
        return {"message": f"Chat room '{chat_room_name}' created"}
    except Exception as e:
        logger.error(f"Error creating chat room: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/join-chat-room")
def join_chat_room(chat_room_name: str = Query(..., description="Chat room name")):
    """
    Returns chat-room history from './chat_history/<chat_room_name>.txt'
    and websocket connection meta-data for the client to initiate connection.
    """
    file_path = os.path.join(CHAT_HISTORY_DIR, f"{chat_room_name}.txt")

    if not os.path.exists(file_path):
        logger.warning(f"Chat room '{chat_room_name}' does not exist.")
        raise HTTPException(status_code=404, detail="Chat room not found")

    try:
        with open(file_path, "r") as f:
            history = [line.strip() for line in f.readlines()]
    except Exception as e:
        logger.error(f"Error reading chat history for room '{chat_room_name}': {e}")
        raise HTTPException(status_code=500, detail="Error retrieving chat history")

    websocket_url = f"ws://localhost:5000/ws/{chat_room_name}"

    return {"chat_room": chat_room_name, "history": history, "websocket_url": websocket_url}


# ====== WebSocket Communication ======
@app.websocket("/ws/{chat_room_name}")
async def websocket_endpoint(websocket: WebSocket, chat_room_name: str):
    """Handles WebSocket connections and broadcasts messages using Redis."""
    await websocket.accept()
    logger.info(f"WebSocket connection established for room: {chat_room_name}")

    # Store connection
    if chat_room_name not in active_connections:
        active_connections[chat_room_name] = []
    active_connections[chat_room_name].append(websocket)

    # Redis Subscription Task
    redis_client_async = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    pubsub = redis_client_async.pubsub()

    try:
        await pubsub.subscribe(chat_room_name)
    except Exception as e:
        logger.error(f"Error subscribing to Redis pub/sub for room {chat_room_name}: {e}")
        await websocket.close()
        return

    async def listen_to_redis():
        """Listen for new messages from Redis and send to WebSocket clients."""
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    logger.info(f"New message in {chat_room_name}: {message['data']}")
                    for ws in active_connections.get(chat_room_name, []):  # Broadcast to all connected clients
                        await ws.send_text(message["data"])
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(chat_room_name)
            await redis_client_async.close()

    redis_task = asyncio.create_task(listen_to_redis())

    try:
        while True:
            data = await websocket.receive_text()

            # Save to file
            file_path = os.path.join(CHAT_HISTORY_DIR, f"{chat_room_name}.txt")
            try:
                with open(file_path, "a") as f:
                    f.write(data + "\n")
                logger.info(f"Message saved to {file_path}")
            except Exception as e:
                logger.error(f"Error writing to file {file_path}: {e}")

            # Publish to Redis (other pods will receive it)
            try:
                await redis_client_async.publish(chat_room_name, data)
                logger.info(f"Message published to Redis channel {chat_room_name}: {data}")
            except Exception as e:
                logger.error(f"Error publishing to Redis: {e}")

    except WebSocketDisconnect:
        logger.warning(f"WebSocket disconnected for room: {chat_room_name}")
        active_connections[chat_room_name].remove(websocket)
        redis_task.cancel()
        await redis_task

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI server on http://0.0.0.0:5000")
    uvicorn.run(app, host="0.0.0.0", port=5000)
