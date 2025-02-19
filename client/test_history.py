import requests
import asyncio
import websockets

BASE_URL = "http://127.0.0.1:5000"
WS_URL = "ws://127.0.0.1:5000/ws"


def test_create_chat_room(chat_room: str):
    """Test creating a chat room."""
    response = requests.post(f"{BASE_URL}/chat-history", params={"chat-room": chat_room})
    print("Create Room Response:", response.json())


def test_get_chat_history(chat_room: str):
    """Test fetching chat history."""
    response = requests.get(f"{BASE_URL}/chat-history", params={"chat-room": chat_room})
    print("Chat History Response:", response.json())


async def test_websocket(chat_room: str):
    """Test WebSocket communication."""
    uri = f"{WS_URL}/{chat_room}"
    async with websockets.connect(uri) as websocket:
        await websocket.send("Hello, this is a test message!")
        response = await websocket.recv()
        print(f"Received: {response}")


if __name__ == "__main__":
    chat_room = "test-room"

    # Test the REST API
    test_create_chat_room(chat_room)
    test_get_chat_history(chat_room)

    # Test WebSocket
    asyncio.run(test_websocket(chat_room))
