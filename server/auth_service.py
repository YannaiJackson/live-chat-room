from fastapi import FastAPI, HTTPException
import pika
import json
import logging
import os
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI()

# RabbitMQ configuration
RABBITMQ_HOST = "localhost"
QUEUE_NAME = "auth_queue"

# File to store registered usernames
USER_FILE = "users.txt"

# Ensure the file exists
if not os.path.exists(USER_FILE):
    with open(USER_FILE, "w") as f:
        pass  # Create an empty file


def get_rabbitmq_channel():
    """Connects to RabbitMQ and returns a channel."""
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)  # Ensure queue exists
    return connection, channel


def is_username_unique(username: str) -> bool:
    """Checks if the username is unique by reading from users.txt."""
    with open(USER_FILE, "r") as f:
        existing_users = {line.strip() for line in f.readlines()}
    return username not in existing_users


def store_username(username: str):
    """Writes a new unique username to users.txt."""
    with open(USER_FILE, "a") as f:
        f.write(username + "\n")


@app.post("/auth")
def authenticate_user(payload: dict):
    username = payload.get("username", "").strip()

    if not username:
        raise HTTPException(status_code=400, detail="Invalid username")

    # Check if the username is unique
    if not is_username_unique(username):
        raise HTTPException(status_code=400, detail="Username already exists")

    try:
        # Store username in file
        store_username(username)

        # Send username to RabbitMQ
        connection, channel = get_rabbitmq_channel()
        message = json.dumps({"username": username})
        channel.basic_publish(exchange="", routing_key=QUEUE_NAME, body=message)
        connection.close()

        logger.info(f"Username '{username}' registered and sent to RabbitMQ")
        return {"message": "User registered successfully"}

    except Exception as e:
        logger.error(f"Error handling username '{username}': {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == '__main__':
    uvicorn.run("auth_service:app", host="127.0.0.1", port=8000, reload=True)
