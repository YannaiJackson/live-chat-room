from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
import os
import uvicorn

app = FastAPI()

CHAT_HISTORY_DIR = "chat_history"
os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)


# Store active WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, room: str, websocket: WebSocket):
        await websocket.accept()
        if room not in self.active_connections:
            self.active_connections[room] = []
        self.active_connections[room].append(websocket)

    def disconnect(self, room: str, websocket: WebSocket):
        self.active_connections[room].remove(websocket)
        if not self.active_connections[room]:
            del self.active_connections[room]

    async def broadcast(self, room: str, message: str):
        if room in self.active_connections:
            for connection in self.active_connections[room]:
                await connection.send_text(message)


manager = ConnectionManager()


@app.get("/chat-history")
async def get_chat_history(chat_room: str = Query(..., alias="chat-room")):
    file_path = os.path.join(CHAT_HISTORY_DIR, f"{chat_room}.txt")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Chat history not found")
    with open(file_path, "r", encoding="utf-8") as file:
        return {"chat_room": chat_room, "history": file.readlines()}


@app.post("/chat-history")
async def create_chat_history(chat_room: str = Query(..., alias="chat-room")):
    file_path = os.path.join(CHAT_HISTORY_DIR, f"{chat_room}.txt")
    if os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="Chat room already exists")
    with open(file_path, "w", encoding="utf-8") as file:
        file.write("")
    return {"message": f"Chat room '{chat_room}' created successfully"}


@app.websocket("/ws/{chat_room}")
async def websocket_endpoint(chat_room: str, websocket: WebSocket):
    await manager.connect(chat_room, websocket)
    file_path = os.path.join(CHAT_HISTORY_DIR, f"{chat_room}.txt")
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as file:
            file.write("")
    try:
        while True:
            message = await websocket.receive_text()
            with open(file_path, "a", encoding="utf-8") as file:
                file.write(message + "\n")
            await manager.broadcast(chat_room, message)
    except WebSocketDisconnect:
        manager.disconnect(chat_room, websocket)

if __name__ == "__main__":
    uvicorn.run("history_service:app", host="127.0.0.1", port=5000, reload=True)