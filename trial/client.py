import asyncio
import json
import websockets


async def send_messages(websocket):
    """Reads user input and sends messages to the server."""
    loop = asyncio.get_running_loop()
    while True:
        message = await loop.run_in_executor(None, input, "")
        await websocket.send(message)


async def receive_messages(websocket):
    """Receives messages from the server and prints them."""
    while True:
        message = await websocket.recv()
        try:
            # Attempt to parse the JSON message from the server.
            data = json.loads(message)
            sender = data.get("sender", "Unknown")
            text = data.get("message", "")
            print(f"{sender}: {text}")
        except Exception as e:
            print(f"An error occurred: {e} \nresponse from server: {message}")


async def main():
    room_name = input("Enter the room name: ")
    client_name = input("Enter your name: ")
    uri = f"ws://127.0.0.1:8000/ws/{room_name}/{client_name}"
    async with websockets.connect(uri) as websocket:
        # Create tasks for sending and receiving messages concurrently.
        send_task = asyncio.create_task(send_messages(websocket))
        receive_task = asyncio.create_task(receive_messages(websocket))
        # Wait until one task completes (usually they run forever).
        done, pending = await asyncio.wait(
            [send_task, receive_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        # Cancel any pending tasks.
        for task in pending:
            task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
