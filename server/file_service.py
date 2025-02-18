import websockets
import asyncio
import json
import os

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)


async def handle_files(websocket, path):
    """Handle file uploads."""
    data = await websocket.recv()
    message = json.loads(data)

    if message.get("command") == "upload":
        filename = message.get("filename")
        filesize = message.get("filesize")
        file_path = os.path.join(UPLOAD_DIR, filename)

        await websocket.send(json.dumps({"status": "ok", "message": "Ready to receive"}))

        with open(file_path, "wb") as f:
            received = 0
            while received < filesize:
                chunk = await websocket.recv()
                f.write(chunk)
                received += len(chunk)

        await websocket.send(json.dumps({"status": "ok", "message": f"File {filename} uploaded!"}))

start_server = websockets.serve(handle_files, "localhost", 8767)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
