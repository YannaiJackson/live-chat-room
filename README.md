# Chat Application

## Functional Requirements
1. **Global Chat Room**  
   - A single public chat room where all users can communicate.  
   - Messages are broadcasted to all connected users.  

2. **Private Chat Rooms**  
   - Users can create and join private chat rooms.  
   - Only invited users can join a private chat room.  

3. **User Identification**  
   - Each user has a unique identifier (username) upon connection.  
   - Usernames are used to track chat messages and actions.  

4. **Chat History Persistence**  
   - The server maintains a record of all messages exchanged in both global and private chat rooms.  
   - Upon entering \ loading a chat room the chat history will be loaded.  

5. **File Upload and Download**  
   - Users can upload files to share within chat rooms.  
   - Other users in the same chat room can download shared files (even multiple files simultaneously).  

## Non-Functional Requirements

1. **Scalability**  
   - The server should support multiple concurrent users.  
   - Efficient message handling and room management.  

2. **Security**  
   - Prevent unauthorized access to private chat rooms.  
   - Secure file transfers and data encryption (if necessary).  

3. **Performance**  
   - Low-latency message delivery.  
   - Optimized database or in-memory storage for chat history.  

4. **Reliability**  
   - Server should handle unexpected client disconnections gracefully.  
   - Error handling and logging for debugging and monitoring.  

## Implementation

1. **Authentication Service**
   - Users connect via WebSocket.
   - Assigns a username and sends it to the Chat Service.
2. **Chat Service**
   - Receives messages from users via WebSocket.
   - Publishes chat messages to RabbitMQ for other services.
   - Subscribes to RabbitMQ to receive messages and broadcasts to WebSocket clients.
3. **History Service**
   - Listens for messages on RabbitMQ.
   - Stores chat messages in the corresponding room’s history file.
4. **File Transfer Service**
   - Handles file uploads and downloads.
   - Uses RabbitMQ to notify about new uploads.


## Future Enhancements

- Implement authentication (e.g., JWT-based login system).
- Store chat history in a database instead of in-memory.
- Add support for end-to-end encryption for private messages.  





Here’s your **`README.md`** file with a clear explanation of your chat system architecture and flow.

---

```md
# Async WebSocket Chat System with RabbitMQ

## Overview
This is a **real-time chat system** built with **Python**, **WebSockets**, and **RabbitMQ**.  
It supports **group chat**, **message broadcasting**, and **authentication handling**.

## **Architecture**
The system consists of **four main components**:

1. **WebSocket Server (Chat Service)**:  
   - Manages WebSocket connections.  
   - Publishes messages to RabbitMQ (`chat_queue`).  
   - Broadcasts messages to connected clients.  

2. **RabbitMQ (Message Broker)**:  
   - Handles communication between services using `auth_queue` and `chat_queue`.  

3. **Auth Listener**:  
   - Listens to `auth_queue` for new users.  
   - Adds authenticated users to the **global** chat room.  

4. **Clients (WebSocket Users)**:  
   - Connect to the WebSocket server.  
   - Send messages and receive real-time chat updates.  

---

## **System Flow**
### **1. User Connects to WebSocket**
- A client connects to the WebSocket server and sends their username.

#### ✅ Example Message:
```json
{"username": "Alice"}
```

#### 📌 System Flow:
```
(Client) → (WebSocket Server)
```

---

### **2. WebSocket Server Registers the User**
- The server stores the username and adds the user to the **global** chat room.

#### 📌 System Flow:
```
(Client) → (WebSocket Server) [Stores user]
```

---

### **3. Authentication Notification via RabbitMQ**
- The WebSocket server publishes the username to the `auth_queue`.

#### ✅ Example RabbitMQ Message:
```json
{"username": "Alice"}
```

#### 📌 System Flow:
```
(WebSocket Server) → (RabbitMQ: auth_queue)
```

---

### **4. Auth Listener Processes the Username**
- The Auth Listener listens for new users and adds them to the **global** chat room.

#### 📌 System Flow:
```
(RabbitMQ: auth_queue) → (Auth Listener) → (User added to global room)
```

---

### **5. User Sends a Chat Message**
- A user sends a message through WebSocket.
- The WebSocket server publishes the message to `chat_queue`.

#### ✅ Example Message:
```json
{"command": "message", "content": "Hello, world!", "room": "global"}
```

#### ✅ RabbitMQ Message:
```json
{"username": "Alice", "room": "global", "content": "Hello, world!"}
```

#### 📌 System Flow:
```
(Client) → (WebSocket Server) → (RabbitMQ: chat_queue)
```

---

### **6. Message Broadcast to Other Users**
- The Chat Service listens to `chat_queue` and sends messages to WebSocket clients in the room.

#### ✅ Example Broadcast:
```json
{"message": "Alice: Hello, world!"}
```

#### 📌 System Flow:
```
(RabbitMQ: chat_queue) → (Chat Service) → (Clients in global room)
```

---

### **7. Clients Receive the Message**
- All users in the same chat room receive the message.

#### 📌 System Flow:
```
(Clients) ← (WebSocket Server) ← (Chat Service)
```

---

## **Final System Flow**
```plaintext
1. (Client) → (WebSocket Server)  [User connects, sends username]
2. (WebSocket Server) → (RabbitMQ: auth_queue)  [Username published]
3. (Auth Listener) ← (RabbitMQ: auth_queue)  [User added to room]
4. (Client) → (WebSocket Server)  [User sends message]
5. (WebSocket Server) → (RabbitMQ: chat_queue)  [Message published]
6. (Chat Service) ← (RabbitMQ: chat_queue)  [Message received]
7. (Clients in room) ← (WebSocket Server)  [Message broadcasted]
```

---

## **Example Scenario**
### **Alice and Bob Join the Chat**
1. **Alice** connects → WebSocket Server registers her → Publishes "Alice" to `auth_queue`.
2. **Bob** connects → WebSocket Server registers him → Publishes "Bob" to `auth_queue`.
3. **Auth Listener** processes both usernames and adds them to the **global** room.

#### ✅ Current State:
- Room "global" = `{Alice, Bob}`
- Both are **connected**.

---

### **Alice Sends a Message**
1. Alice sends:  
   ```json
   {"command": "message", "content": "Hello, Bob!", "room": "global"}
   ```
2. **Chat Service** sends this to `chat_queue`.
3. **Chat Service** consumes the message and sends:
   ```json
   {"message": "Alice: Hello, Bob!"}
   ```
   → **to both Alice and Bob** via WebSocket.

#### ✅ Now Bob Sees:
```
Alice: Hello, Bob!
```

---

## **Key Features**
✅ **Real-Time Communication**: Messages are instantly processed using WebSockets and RabbitMQ.  
✅ **Decoupled Services**: Authentication and chat messaging are handled separately.  
✅ **Scalability**: Can be extended with private rooms, file sharing, etc.  
✅ **Asynchronous Processing**: RabbitMQ ensures non-blocking message handling.  

---