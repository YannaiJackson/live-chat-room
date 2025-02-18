import socket
import threading
import json
import os

HOST = '127.0.0.1'
PORT = 12345


def receive_messages(sock):
    """
    Continuously receive messages from the server and print them.
    """
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                break
            print(data.decode())
        except Exception as e:
            print("Error receiving data:", e)
            break


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))

    # Start a thread to listen for server messages
    threading.Thread(target=receive_messages, args=(sock,), daemon=True).start()

    # Wait for server prompt for username and then send it
    username = input("Enter your username: ")
    sock.sendall(username.encode())

    print("Commands should be entered as valid JSON. Examples:")
    print('  Send a message: {"command": "message", "content": "Hello everyone!"}')
    print('  Create a room: {"command": "create_room", "room": "room1"}')
    print('  Join a room:   {"command": "join_room", "room": "room1"}')
    print('  Upload a file: {"command": "upload", "filename": "path\to\file.txt"}')
    print('  Download a file: {"command": "download", "filename": "test.txt"}')

    while True:
        user_input = input()
        try:
            message = json.loads(user_input)
        except json.JSONDecodeError:
            print("Invalid JSON. Please try again.")
            continue

        command = message.get("command")
        if command == "upload":
            # For file upload, add file size info and then send file data.
            filename = message.get("filename")
            if not filename or not os.path.exists(filename):
                print("File not found.")
                continue
            filesize = os.path.getsize(filename)
            message["filesize"] = filesize
            sock.sendall(json.dumps(message).encode())
            # Wait for the server to be ready
            ack = sock.recv(1024).decode()
            if ack == "READY":
                with open(filename, "rb") as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk:
                            break
                        sock.sendall(chunk)
                print(f"Uploaded file '{filename}'.")
            else:
                print("Server did not acknowledge file upload.")
        else:
            # For other commands, simply send the JSON message
            sock.sendall(json.dumps(message).encode())


if __name__ == "__main__":
    main()
