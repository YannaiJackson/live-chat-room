import asyncio
import websockets
import json
import pika

HOST = "localhost"
PORT = 8765  # WebSocket Port
RABBITMQ_HOST = "localhost"

# Maintain active user connections
active_users = {}


async def handle_connection(websocket, path):
    """Handle user authentication and notify Chat Service."""
    try:
        # Receive authentication request
        data = await websocket.recv()
        request = json.loads(data)
        username = request.get("username")

        if not username or username in active_users:
            await websocket.send(json.dumps({"status": "error", "message": "Username taken"}))
            return

        active_users[username] = websocket
        await websocket.send(json.dumps({"status": "ok", "message": f"Welcome, {username}!"}))

        # Notify Chat Service via RabbitMQ
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue="auth_notifications")
        channel.basic_publish(exchange="", routing_key="auth_notifications", body=json.dumps({"username": username}))
        connection.close()

        # Keep connection open
        await websocket.wait_closed()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if username in active_users:
            del active_users[username]

# Start WebSocket Server
start_server = websockets.serve(handle_connection, HOST, PORT)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
