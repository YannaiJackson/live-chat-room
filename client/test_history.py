import asyncio
import websockets
import json
import aiohttp

SERVER_URL = "http://localhost:5000"


def print_menu():
    print("\nOptions:")
    print("1. Create chat room -> {\"username\": \"your_name\", \"create\": \"chat_room_name\"}")
    print("2. Join chat room -> {\"username\": \"your_name\", \"join\": \"chat_room_name\"}")
    print("3. Send message -> {\"username\": \"your_name\", \"message\": \"your_message\"}")


async def create_room(session, command):
    """Sends a request to create a chat room."""
    endpoint = "/create-chat-room"
    payload = {
        "username": command["username"],
        "chat_room_name": command["create"]
    }
    async with session.post(SERVER_URL + endpoint, json=payload) as response:
        if response.status == 200:
            data = await response.json()
            print(f"\nCreated chat room: {data['chat_room']}")
            return data.get("websocket_url")
        else:
            print(f"Error: {await response.text()}")
            return None


async def join_room(session, command):
    """Sends a request to join a chat room and returns the WebSocket URL."""
    endpoint = "/join-chat-room"
    payload = {
        "username": command["username"],
        "chat_room_name": command["join"]
    }
    async with session.post(SERVER_URL + endpoint, json=payload) as response:
        if response.status == 200:
            data = await response.json()
            print(f"\nJoined chat room: {data['chat_room']}")
            print("\nChat History:")
            for msg in data["history"]:
                print(msg)
            return data.get("websocket_url")
        else:
            print(f"Error: {await response.text()}")
            return None


async def send_message(websocket, username):
    """Handles sending messages via WebSocket."""
    while True:
        try:
            user_input = input("Enter JSON command: ")
            if user_input.lower() == "exit":
                print("Exiting chat...")
                break

            try:
                command = json.loads(user_input)
            except json.JSONDecodeError:
                print("Invalid JSON format. Try again.")
                continue

            if "message" in command:
                message_data = {
                    "username": command.get("username", username),
                    "message": command["message"]
                }
                await websocket.send(json.dumps(message_data))
            else:
                print("Invalid command format. Use {\"username\": \"your_name\", \"message\": \"text\"}")
        except Exception as e:
            print(f"Error sending message: {e}")
            break


async def receive_messages(websocket):
    """Handles receiving messages from WebSocket."""
    try:
        async for message in websocket:
            print(f"\n{message}")
    except websockets.exceptions.ConnectionClosed:
        print("Connection closed.")


async def handle_chat(websocket_url, username):
    """Handles WebSocket connection for chatting."""
    async with websockets.connect(websocket_url) as websocket:
        print("Connected to chat room. Start sending messages!")
        await asyncio.gather(
            send_message(websocket, username),
            receive_messages(websocket)
        )


async def main():
    """Main CLI loop to handle user commands."""
    print_menu()
    async with aiohttp.ClientSession() as session:
        while True:
            user_input = input("\nEnter JSON command: ")
            try:
                command = json.loads(user_input)
            except json.JSONDecodeError:
                print("Invalid JSON format. Try again.")
                continue

            ws_url = None
            if "create" in command:
                ws_url = await create_room(session, command)
            elif "join" in command:
                ws_url = await join_room(session, command)

            if ws_url:
                await handle_chat(ws_url, command["username"])
            else:
                print("Invalid command format. Check the menu for correct format.")

if __name__ == "__main__":
    asyncio.run(main())
