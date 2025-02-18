from fastapi import FastAPI, Query, HTTPException
import pika
import logging
import threading
import os
import uvicorn
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# RabbitMQ configuration
RABBITMQ_HOST = "localhost"
CHAT_HISTORY_QUEUE = "chat_history_queue"  # Ensure the Chat Service publishes to this queue

# Directory to store chat messages by room
CHAT_HISTORY_DIR = "chat_history"

# Ensure the chat_history directory exists
os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)


def store_message(message_data: dict):
    """
    Appends the received message data to the file corresponding to its chat room.
    The message_data should contain:
      - room: chat room identifier
      - username: sender of the message
      - message: the text content of the message
    """
    room = message_data.get("room")
    if not room:
        logger.error("Received message without a room specified.")
        return

    file_path = os.path.join(CHAT_HISTORY_DIR, f"{room}.txt")
    try:
        with open(file_path, "a", encoding="utf-8") as f:
            # Store the message as a JSON line for consistency
            f.write(json.dumps(message_data) + "\n")
        logger.info(f"Stored message for room '{room}'.")
    except Exception as e:
        logger.error(f"Error storing message in room '{room}': {e}")


def callback(ch, method, properties, body):
    """
    Called when a message is consumed from RabbitMQ.
    The message is expected to be a JSON string containing chat data.
    """
    try:
        message_str = body.decode("utf-8")
        message_data = json.loads(message_str)
        logger.info(f"Received message: {message_data}")
        store_message(message_data)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        # Optionally, add a negative acknowledgement here if needed.


def start_rabbitmq_consumer():
    """
    Connects to RabbitMQ and starts consuming messages.
    Runs in a separate thread since it is a blocking call.
    """
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST)
        )
        channel = connection.channel()
        channel.queue_declare(queue=CHAT_HISTORY_QUEUE, durable=True)
        channel.basic_qos(prefetch_count=1)  # Fair dispatch
        channel.basic_consume(queue=CHAT_HISTORY_QUEUE, on_message_callback=callback)
        logger.info(f" [*] Waiting for messages on queue '{CHAT_HISTORY_QUEUE}'.")
        channel.start_consuming()
    except Exception as e:
        logger.error(f"RabbitMQ consumer error: {e}")
        # Optionally, implement retry logic here.


@app.get("/history")
def get_history(room: str = Query(..., description="Chat room identifier to filter messages")):
    """
    Returns the chat history for the specified room.
    It reads from the file chat_history/<room>.txt.
    """
    file_path = os.path.join(CHAT_HISTORY_DIR, f"{room}.txt")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"No history found for room '{room}'.")
    
    messages_for_room = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        message_data = json.loads(line.strip())
                        messages_for_room.append(message_data)
                    except json.JSONDecodeError:
                        logger.error("Skipping malformed message line.")
        return {"room": room, "messages": messages_for_room}
    except Exception as e:
        logger.error(f"Error reading history for room '{room}': {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.on_event("startup")
def on_startup():
    """
    Start the RabbitMQ consumer in a background thread on startup.
    """
    consumer_thread = threading.Thread(target=start_rabbitmq_consumer, daemon=True)
    consumer_thread.start()


if __name__ == "__main__":
    uvicorn.run("history_service:app", host="127.0.0.1", port=8001, reload=True)
