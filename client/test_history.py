import json
import requests
import asyncio
import websockets

SERVER_URL = "http://localhost:5000"


async def receive_messages(ws):
    """Continuously receive and display messages from the WebSocket."""
    try:
        while True:
            message = await ws.recv()
            print(f"\n[New Message] {message}")
    except Exception as e:
        print(f"WebSocket error: {e}")


async def main():
    current_websocket = None  # We'll store the active connection here

    while True:
        try:
            print("""Options:\n{"create": "<chat-room-name>"}\n{"join": "<chat-room-name>"}\n{"message": "<message-content>"}
            (Upon creating / joining a chat-room the user automatically exists the current chat-room)""")
            command_input = input("Enter Command: ").strip()
            if not command_input:
                continue

            command = json.loads(command_input)

            # --- Create Chat Room and Join ---
            if "create" in command:
                room_name = command["create"]
                # Create the chat room via the POST endpoint
                create_resp = requests.post(
                    f"{SERVER_URL}/create-chat-room",
                    json={"chat_room_name": room_name}
                )
                print(f"Create response: {create_resp.json()}")

                # Join the chat room automatically
                join_resp = requests.get(
                    f"{SERVER_URL}/join-chat-room",
                    params={"chat_room_name": room_name}
                )
                if join_resp.status_code != 200:
                    print("Error joining chat room:", join_resp.json())
                    continue
                data = join_resp.json()
                print("Chat History:")
                for msg in data.get("history", []):
                    print(msg)

                # Use the WebSocket URL from the response to connect
                websocket_url = data.get("websocket_url")
                current_websocket = await websockets.connect(websocket_url)
                print(f"Connected to chat room '{room_name}' via WebSocket.")
                asyncio.create_task(receive_messages(current_websocket))

            # --- Join Existing Chat Room ---
            elif "join" in command:
                room_name = command["join"]
                join_resp = requests.get(
                    f"{SERVER_URL}/join-chat-room",
                    params={"chat_room_name": room_name}
                )
                if join_resp.status_code != 200:
                    print("Error joining chat room:", join_resp.json())
                    continue
                data = join_resp.json()
                print("Chat History:")
                for msg in data.get("history", []):
                    print(msg)

                # Connect using the received WebSocket URL
                websocket_url = data.get("websocket_url")
                current_websocket = await websockets.connect(websocket_url)
                print(f"Connected to chat room '{room_name}' via WebSocket.")
                asyncio.create_task(receive_messages(current_websocket))

            # --- Send a Message ---
            elif "message" in command:
                if current_websocket is None:
                    print("You are not connected to any chat room. Please join or create one first.")
                    continue
                message_content = command["message"]
                await current_websocket.send(message_content)
                print(f"Message sent: {message_content}")

            else:
                print("Unknown command. Please use 'create', 'join', or 'message'.")
        except KeyboardInterrupt:
            print("\nExiting chat client.")
            break
        except Exception as e:
            print(f"An error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
