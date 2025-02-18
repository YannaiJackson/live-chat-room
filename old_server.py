import socket
import threading
import json
import os

HOST = '127.0.0.1'
PORT = 12345

clients = {}         # username -> client_socket
client_rooms = {}    # username -> current room name
rooms = {"global": set()}  # room name -> set of usernames
chat_history = {"global": []}  # room name -> list of message strings
lock = threading.Lock()

# Directory for storing uploaded files
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Directory for storing chat history files
HISTORY_DIR = "history"
if not os.path.exists(HISTORY_DIR):
    os.makedirs(HISTORY_DIR)


def broadcast(message, room):
    """
    Broadcast a message to all clients in the specified room.
    """
    if room not in rooms:
        return
    for user in rooms[room]:
        client = clients.get(user)
        if client:
            try:
                client.sendall(message.encode())
            except Exception as e:
                print(f"Error sending message to {user}: {e}")


def handle_client(client_socket, address):
    global clients, client_rooms, rooms, chat_history
    username = None
    try:
        # Ask for username
        client_socket.sendall("Please enter your username: ".encode())
        username = client_socket.recv(1024).decode().strip()
        with lock:
            while not username or username in clients:
                client_socket.sendall("Username taken or invalid. Enter another username: ".encode())
                username = client_socket.recv(1024).decode().strip()
            clients[username] = client_socket
            # Join the global chat room by default
            client_rooms[username] = "global"
            rooms["global"].add(username)
            if "global" not in chat_history:
                chat_history["global"] = []

        client_socket.sendall(f"Welcome {username}! You are in the global chat room.\n".encode())
        # Send chat history for the global room
        history = "\n".join(chat_history["global"])
        if history:
            client_socket.sendall(f"Chat History:\n{history}\n".encode())

        # Main loop for client messages
        while True:
            data = client_socket.recv(4096)
            if not data:
                break
            try:
                message = json.loads(data.decode())
            except json.JSONDecodeError:
                client_socket.sendall("Invalid JSON format.\n".encode())
                continue

            # Process message by command
            command = message.get("command")
            if command == "message":
                content = message.get("content", "")
                room = client_rooms.get(username, "global")
                msg_line = f"{username}: {content}"
                with lock:
                    chat_history.setdefault(room, []).append(msg_line)
                    # Append to a file for persistence (one file per room in the history folder)
                    history_path = os.path.join(HISTORY_DIR, f"{room}_history.txt")
                    with open(history_path, "a") as f:
                        f.write(msg_line + "\n")
                broadcast(msg_line, room)
            elif command == "create_room":
                # Create and join a private room
                room = message.get("room")
                if not room:
                    client_socket.sendall("No room name provided.\n".encode())
                    continue
                with lock:
                    if room not in rooms:
                        rooms[room] = set()
                        chat_history[room] = []
                        # Remove user from previous room and join new one
                        old_room = client_rooms.get(username, "global")
                        if username in rooms[old_room]:
                            rooms[old_room].remove(username)
                        client_rooms[username] = room
                        rooms[room].add(username)
                        client_socket.sendall(f"Room '{room}' created and joined.\n".encode())
                    else:
                        client_socket.sendall(f"Room '{room}' already exists.\n".encode())
            elif command == "join_room":
                # Join an existing room
                room = message.get("room")
                if not room:
                    client_socket.sendall("No room name provided.\n".encode())
                    continue
                with lock:
                    if room in rooms:
                        # Remove user from the old room
                        old_room = client_rooms.get(username, "global")
                        if username in rooms[old_room]:
                            rooms[old_room].remove(username)
                        # Join the new room
                        client_rooms[username] = room
                        rooms[room].add(username)
                        client_socket.sendall(f"Joined room '{room}'.\n".encode())
                        # Send room's chat history
                        history = "\n".join(chat_history.get(room, []))
                        if history:
                            client_socket.sendall(f"Chat History for {room}:\n{history}\n".encode())
                    else:
                        client_socket.sendall(f"Room '{room}' does not exist.\n".encode())
            elif command == "upload":
                # Handle file upload
                room = client_rooms.get(username, "global")
                filename = message.get("filename")
                filesize = message.get("filesize")
                if not filename or not filesize:
                    client_socket.sendall("Filename or filesize not provided.\n".encode())
                    continue
                # Signal client to start sending file data
                client_socket.sendall("READY".encode())
                received = 0
                file_path = os.path.join(UPLOAD_DIR, filename)
                with open(file_path, "wb") as f:
                    while received < filesize:
                        chunk = client_socket.recv(min(4096, filesize - received))
                        if not chunk:
                            break
                        f.write(chunk)
                        received += len(chunk)
                info = f"{username} uploaded file: {filename}"
                with lock:
                    chat_history.setdefault(room, []).append(info)
                    history_path = os.path.join(HISTORY_DIR, f"{room}_history.txt")
                    with open(history_path, "a") as f:
                        f.write(info + "\n")
                broadcast(info, room)
            elif command == "download":
                # Send a file to the client
                filename = message.get("filename")
                if not filename:
                    client_socket.sendall("Filename not provided.\n".encode())
                    continue
                file_path = os.path.join(UPLOAD_DIR, filename)
                if os.path.exists(file_path):
                    filesize = os.path.getsize(file_path)
                    # Send file size information first
                    client_socket.sendall(json.dumps({"filesize": filesize}).encode())
                    ack = client_socket.recv(1024)  # expecting ack "READY"
                    with open(file_path, "rb") as f:
                        while True:
                            chunk = f.read(4096)
                            if not chunk:
                                break
                            client_socket.sendall(chunk)
                else:
                    client_socket.sendall("File not found.\n".encode())
            else:
                client_socket.sendall("Unknown command.\n".encode())
    except Exception as e:
        print(f"Error with client {address}: {e}")
    finally:
        with lock:
            if username in clients:
                del clients[username]
            room = client_rooms.get(username, "global")
            if room in rooms and username in rooms[room]:
                rooms[room].remove(username)
            if username in client_rooms:
                del client_rooms[username]
        client_socket.close()
        print(f"Connection with {address} closed.")


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"Server listening on {HOST}:{PORT}")
    try:
        while True:
            client_sock, addr = server_socket.accept()
            print(f"New connection from {addr}")
            client_thread = threading.Thread(target=handle_client, args=(client_sock, addr))
            client_thread.daemon = True
            client_thread.start()
    except KeyboardInterrupt:
        print("Server shutting down.")
    finally:
        server_socket.close()


if __name__ == "__main__":
    start_server()
