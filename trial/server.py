import asyncio
import json
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis_client = redis.from_url("redis://localhost", decode_responses=True)
    yield
    await app.state.redis_client.close()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

room_listeners: Dict[str, asyncio.Task] = {}


class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, room_name: str, websocket: WebSocket):
        await websocket.accept()
        if room_name not in self.rooms:
            self.rooms[room_name] = []
        self.rooms[room_name].append(websocket)

    def disconnect(self, room_name: str, websocket: WebSocket):
        if room_name in self.rooms and websocket in self.rooms[room_name]:
            self.rooms[room_name].remove(websocket)
            if not self.rooms[room_name]:
                del self.rooms[room_name]
                if room_name in room_listeners:
                    room_listeners[room_name].cancel()
                    del room_listeners[room_name]

    async def send_message(self, room_name: str, message: str):
        if room_name in self.rooms:
            for connection in self.rooms[room_name]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    print(f"Error sending message: {e}")


manager = ConnectionManager()


async def redis_listener(room_name: str, redis_client: redis.Redis):
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(room_name)
    try:
        async for message in pubsub.listen():
            if message.get("type") == "message":
                data = message.get("data")
                await manager.send_message(room_name, data)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Redis listener error in room {room_name}: {e}")
    finally:
        await pubsub.unsubscribe(room_name)
        await pubsub.close()


@app.websocket("/ws/{room_name}/{client_name}")
async def websocket_endpoint(websocket: WebSocket, room_name: str, client_name: str):
    redis_client: Optional[redis.Redis] = getattr(websocket.app.state, "redis_client", None)

    is_new_room = room_name not in manager.rooms  # Check if this is a new room

    await manager.connect(room_name, websocket)

    if redis_client and room_name not in room_listeners:
        room_listeners[room_name] = asyncio.create_task(redis_listener(room_name, redis_client))

    if is_new_room and redis_client:
        create_message = json.dumps({"sender": "Server", "message": f"🟢 {client_name} created {room_name}"})
        await redis_client.publish(room_name, create_message)

    join_message = json.dumps({"sender": "Server", "message": f"🔵 {client_name} joined {room_name}"})
    if redis_client:
        await redis_client.publish(room_name, join_message)

    try:
        while True:
            data = await websocket.receive_text()
            chat_message = json.dumps({"sender": client_name, "message": data})
            if redis_client:
                await redis_client.publish(room_name, chat_message)
    except WebSocketDisconnect:
        manager.disconnect(room_name, websocket)
        leave_message = json.dumps({"sender": "Server", "message": f"🔵 {client_name} left {room_name}"})
        if redis_client:
            await redis_client.publish(room_name, leave_message)
    except Exception as e:
        print(f"Unexpected error in {room_name}: {e}")
        manager.disconnect(room_name, websocket)
        error_message = json.dumps({"sender": "Server", "message": f"🔴 {client_name} encountered an error in {room_name}"})
        if redis_client:
            await redis_client.publish(room_name, error_message)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
