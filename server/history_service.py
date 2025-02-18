import pika
import json
import os

HISTORY_DIR = "history"
if not os.path.exists(HISTORY_DIR):
    os.makedirs(HISTORY_DIR)


def callback(ch, method, properties, body):
    """Save chat messages to a file."""
    data = json.loads(body)
    room = data["room"]
    message = data["message"]

    file_path = os.path.join(HISTORY_DIR, f"{room}_history.txt")
    with open(file_path, "a") as f:
        f.write(message + "\n")


connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
channel = connection.channel()
channel.queue_declare(queue="chat_history")
channel.basic_consume(queue="chat_history", on_message_callback=callback, auto_ack=True)

print("History Service running...")
channel.start_consuming()
