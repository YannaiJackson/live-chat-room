import requests
import websockets
import json
import asyncio
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Logs to console
        logging.FileHandler("client.log")  # Logs to file
    ]
)
logger = logging.getLogger(__name__)

# Base URL for the services
AUTH_SERVICE_URL = "http://127.0.0.1:8000/auth"
CHAT_SERVICE_URL = "ws://127.0.0.1:8002/ws"

# Function to authenticate a user
def authenticate_user(username: str):
    payload = {"username": username}
    try:
        logger.info(f"Attempting to authenticate user '{username}'...")
        response = requests.post(AUTH_SERVICE_URL, json=payload)
        if response.status_code == 200:
            logger.info(f"User '{username}' registered successfully.")
            return True
        else:
            logger.error(f"Error registering user: {response.json()['detail']}")
            return False
    except Exception as e:
        logger.error(f"Error communicating with auth service: {e}")
        return False


# Function to connect to the chat service via WebSocket
async def connect_to_chat_service(username: str):
    try:
        logger.info(f"Connecting to chat service as {username}...")
        async with websockets.connect(f"{CHAT_SERVICE_URL}/{username}") as websocket:
            logger.info(f"Connected to chat service as {username}")
            await chat_service(websocket)
    except Exception as e:
        logger.error(f"Error connecting to chat service: {e}")


# Function to handle the chat flow
async def chat_service(websocket):
    try:
        while True:
            command = input("Enter command (message, create_room, join_room, exit): ").strip().lower()
            if command == "message":
                content = input("Enter message: ")
                message_data = {
                    "command": "message",
                    "content": content
                }
                await websocket.send(json.dumps(message_data))
                logger.info(f"Sent message: {content}")

            elif command == "create_room":
                room_name = input("Enter room name to create: ")
                message_data = {
                    "command": "create_room",
                    "room": room_name
                }
                await websocket.send(json.dumps(message_data))
                response = await websocket.recv()
                logger.info(f"Response: {response}")

            elif command == "join_room":
                room_name = input("Enter room name to join: ")
                message_data = {
                    "command": "join_room",
                    "room": room_name
                }
                await websocket.send(json.dumps(message_data))
                response = await websocket.recv()
                logger.info(f"Response: {response}")

            elif command == "exit":
                logger.info(f"Exiting chat as {username}.")
                break

            else:
                logger.warning("Invalid command.")

    except websockets.exceptions.ConnectionClosedError as e:
        logger.error(f"Connection closed: {e}")
    except Exception as e:
        logger.error(f"Error in chat service: {e}")


# Main function to run the client
def main():
    username = input("Enter a username to authenticate: ").strip()

    # Authenticate user first
    if authenticate_user(username):
        # If authentication is successful, connect to the chat service
        asyncio.run(connect_to_chat_service(username))


if __name__ == "__main__":
    main()
