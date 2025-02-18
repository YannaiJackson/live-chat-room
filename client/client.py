import asyncio
import websockets
import json
import os

AUTH_SERVER = "ws://localhost:8765"
CHAT_SERVER = "ws://localhost:8766"
HISTORY_SERVER = "ws://localhost:8768"
FILE_SERVER = "ws://localhost:8767"


class ChatClient:
    def __init__(self):
        self.username = None
        self.chat_ws = None
        self.current_room = "global"

    async def authenticate(self):
        """Handle user authentication via WebSocket."""
        async with websockets.connect(AUTH_SERVER) as ws:
            while True:
                username = input("Enter your username: ")
                await ws.send(json.dumps({"username": username}))
                response = json.loads(await ws.recv())

                if response["status"] == "ok":
                    self.username = username
                    print(response["message"])
                    break
                else:
                    print(response["message"])

    async def connect_to_chat(self):
        """Connect to the Chat Service WebSocket."""
        self.chat_ws = await websockets.connect(CHAT_SERVER)
        await self.chat_ws.send(json.dumps({"username": self.username}))

    async def send_message(self, message):
        """Send a chat message to the current room."""
        msg = json.dumps({"command": "message", "room": self.current_room, "content": message})
        await self.chat_ws.send(msg)

    async def create_room(self, room_name):
        """Create a new chat room."""
        await self.chat_ws.send(json.dumps({"command": "create_room", "room": room_name}))
        print(f"Room '{room_name}' created and joined.")

    async def join_room(self, room_name):
        """Join an existing chat room and fetch its history."""
        await self.chat_ws.send(json.dumps({"command": "join_room", "room": room_name}))
        self.current_room = room_name

        # Fetch chat history from History Service
        async with websockets.connect(HISTORY_SERVER) as ws:
            await ws.send(json.dumps({"command": "get_history", "room": room_name}))
            history = json.loads(await ws.recv())

            print(f"\n--- Chat History for {room_name} ---")
            for message in history.get("messages", []):
                print(message)
            print("--------------------------------")

    async def listen_for_messages(self):
        """Listen for incoming messages."""
        while True:
            response = json.loads(await self.chat_ws.recv())
            print(f"\n[{response['room']}] {response['message']}")

    async def upload_file(self, file_path):
        """Upload a file to the server."""
        if not os.path.exists(file_path):
            print("File not found.")
            return

        filename = os.path.basename(file_path)
        filesize = os.path.getsize(file_path)

        async with websockets.connect(FILE_SERVER) as ws:
            await ws.send(json.dumps({"command": "upload", "filename": filename, "filesize": filesize}))
            response = json.loads(await ws.recv())

            if response["status"] == "ok":
                print("Uploading file...")
                with open(file_path, "rb") as f:
                    while chunk := f.read(4096):
                        await ws.send(chunk)
                print("File uploaded successfully.")

    async def start(self):
        """Start the chat client."""
        await self.authenticate()
        await self.connect_to_chat()

        print("\nCommands:")
        print("/exit - Leave the chat")
        print("/create <room> - Create a room")
        print("/join <room> - Join a room and load history")
        print("/upload <file> - Upload a file")

        # Listen for messages in a background task
        asyncio.create_task(self.listen_for_messages())

        while True:
            user_input = input("> ")
            if user_input.startswith("/exit"):
                break
            elif user_input.startswith("/create"):
                _, room_name = user_input.split(maxsplit=1)
                await self.create_room(room_name)
            elif user_input.startswith("/join"):
                _, room_name = user_input.split(maxsplit=1)
                await self.join_room(room_name)
            elif user_input.startswith("/upload"):
                _, file_path = user_input.split(maxsplit=1)
                await self.upload_file(file_path)
            else:
                await self.send_message(user_input)


if __name__ == "__main__":
    client = ChatClient()
    asyncio.run(client.start())
