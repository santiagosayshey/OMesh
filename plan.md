## Overview

The implementation will consist of two main components:

1. **Server Application**: Handles client connections, inter-server communication, message routing, and file transfers.
2. **Client Application**: Connects to a server, sends and receives messages, handles encryption/decryption, and interacts with the user through a basic HTML frontend.

Both components will utilize WebSockets for communication and implement the specified encryption schemes using RSA and AES algorithms.

---

## Technologies and Libraries

- **Python 3.8+**
- **WebSockets**: `websockets` library for asynchronous WebSocket handling.
- **HTTP Server**: `aiohttp` or `Flask` for handling HTTP requests (file uploads/downloads).
- **Cryptography**: `cryptography` library for RSA and AES implementations.
- **Frontend**: Basic HTML served via the client application, possibly using `Flask` or `aiohttp` for simplicity.

---

## Directory Structure

```
project/
├── server/
│   ├── server.py
│   ├── server_utils.py
│   ├── clients/
│   └── files/
├── client/
│   ├── client.py
│   ├── client_utils.py
│   ├── templates/
│   │   └── index.html
│   └── static/
├── common/
│   ├── crypto.py
│   └── protocol.py
└── README.md
```

---

## Component Details

### 1. Common Module (`common/`)

#### a. `protocol.py`

Defines constants, message formats, and utility functions for message construction and parsing.

- **Classes/Functions**:
  - `MessageType`: Enum class for message types (`HELLO`, `CHAT`, `PUBLIC_CHAT`, etc.).
  - `build_signed_message(data_dict, private_key, counter)`: Constructs a signed message.
  - `verify_signed_message(message_dict, public_key, expected_counter)`: Verifies a signed message.

#### b. `crypto.py`

Handles all cryptographic operations.

- **Functions**:
  - `generate_rsa_key_pair()`: Generates RSA key pair.
  - `load_public_key(pem_data)`: Loads RSA public key from PEM.
  - `load_private_key(pem_data)`: Loads RSA private key from PEM.
  - `sign_data(data_bytes, private_key)`: Signs data using RSA-PSS.
  - `verify_signature(data_bytes, signature_bytes, public_key)`: Verifies RSA-PSS signature.
  - `encrypt_rsa_oaep(data_bytes, public_key)`: Encrypts data using RSA-OAEP.
  - `decrypt_rsa_oaep(cipher_bytes, private_key)`: Decrypts data using RSA-OAEP.
  - `encrypt_aes_gcm(plaintext_bytes, key_bytes, iv_bytes)`: Encrypts data using AES-GCM.
  - `decrypt_aes_gcm(cipher_bytes, key_bytes, iv_bytes)`: Decrypts data using AES-GCM.
  - `calculate_fingerprint(public_key)`: Calculates SHA-256 hash of the public key.

### 2. Server Application (`server/`)

#### a. `server.py`

Main server application handling client connections, inter-server communication, and message routing.

- **Classes**:
  - `Server`:
    - **Attributes**:
      - `address`: Server's own address.
      - `neighbour_addresses`: List of addresses of other servers in the neighbourhood.
      - `clients`: Dictionary mapping client fingerprints to their connection info.
      - `servers`: Dictionary mapping server addresses to their WebSocket connections.
      - `client_counters`: Dictionary tracking last counter value for each client.
      - `client_public_keys`: Dictionary mapping client fingerprints to their public keys.
    - **Methods**:
      - `start()`: Starts the server's WebSocket and HTTP servers.
      - `handle_client_connection(websocket, path)`: Coroutine to handle incoming client connections.
      - `handle_server_connection(websocket, path)`: Coroutine to handle incoming server connections.
      - `connect_to_neighbours()`: Connects to other servers in the neighbourhood.
      - `broadcast_client_update()`: Sends `client_update` messages to all servers.
      - `handle_client_message(websocket, message)`: Processes messages from clients.
      - `handle_server_message(websocket, message)`: Processes messages from servers.
      - `handle_file_upload(request)`: Handles HTTP file upload.
      - `handle_file_download(request)`: Handles HTTP file download.

#### b. `server_utils.py`

Utility functions specific to the server.

- **Functions**:
  - `parse_message(message_str)`: Parses incoming JSON messages.
  - `validate_message_format(message_dict)`: Validates message structure according to protocol.
  - `update_client_list(client_list)`: Updates the server's internal client list.
  - `forward_message(destination_server, message)`: Forwards messages to other servers.

### 3. Client Application (`client/`)

#### a. `client.py`

Main client application handling user interaction, message sending/receiving, and encryption/decryption.

- **Classes**:
  - `Client`:
    - **Attributes**:
      - `server_address`: Address of the connected server.
      - `websocket`: WebSocket connection to the server.
      - `private_key`: Client's RSA private key.
      - `public_key`: Client's RSA public key.
      - `counter`: Monotonically increasing counter.
      - `known_clients`: Dictionary of known clients and their public keys.
    - **Methods**:
      - `start()`: Starts the client application and frontend server.
      - `connect_to_server()`: Establishes WebSocket connection to the server.
      - `send_hello()`: Sends `hello` message to the server.
      - `send_chat_message(recipients, message_text)`: Sends encrypted chat messages.
      - `send_public_chat(message_text)`: Sends public chat messages.
      - `request_client_list()`: Sends `client_list_request` to the server.
      - `receive_messages()`: Coroutine to handle incoming messages.
      - `handle_incoming_message(message)`: Processes messages from the server.
      - `encrypt_message(message_text, recipient_public_keys)`: Encrypts messages.
      - `decrypt_message(encrypted_message, symm_key, iv)`: Decrypts messages.

#### b. `client_utils.py`

Utility functions specific to the client.

- **Functions**:
  - `render_template(template_name, context)`: Renders HTML templates.
  - `serve_static_file(file_path)`: Serves static files (if needed).
  - `parse_server_response(message_dict)`: Parses responses from the server.

#### c. `templates/index.html`

A basic HTML file to interact with the client application.

- **Features**:
  - Input field for entering messages.
  - Display area for showing received messages.
  - Button to request client list.
  - List of online clients.
  - Minimal styling using inline CSS or a basic stylesheet.

### 4. Frontend Server (Within `client.py`)

- **Uses**: `Flask` or `aiohttp` to serve the HTML frontend and handle user interactions.
- **Endpoints**:
  - `/`: Serves the main HTML page.
  - `/send_message`: Handles form submission for sending messages.
  - `/get_messages`: API endpoint to fetch new messages asynchronously (optional).
  - `/get_clients`: API endpoint to fetch the list of online clients.

---

## Detailed Implementation Steps

### Step 1: Setup Project Structure

- Create the directory structure as outlined.
- Initialize `__init__.py` files if needed for module imports.

### Step 2: Implement Cryptographic Functions (`common/crypto.py`)

- Use the `cryptography` library to implement RSA and AES functions according to the specified parameters.
- Ensure keys are generated/stored securely.

### Step 3: Define Protocol Messages (`common/protocol.py`)

- Create an enumeration for message types.
- Define functions to build and parse messages, including signature handling and counter management.

### Step 4: Implement the Server Application (`server/server.py`)

#### a. WebSocket Server

- Use `asyncio` and `websockets` to accept client and server connections on different endpoints (e.g., `/client`, `/server`).
- Implement `handle_client_connection` to process client messages.
- Implement `handle_server_connection` to process server messages.

#### b. Client Management

- Store connected clients and their public keys upon receiving a `hello` message.
- Update client lists upon disconnections and send `client_update` messages to other servers.

#### c. Inter-Server Communication

- Establish connections to other servers in the neighbourhood.
- Handle `client_update_request` and respond with `client_update`.
- Forward messages to appropriate destination servers based on `destination_servers` field.

#### d. Message Routing

- Upon receiving a message from a client, determine the destination server(s) and forward accordingly.
- For incoming messages from other servers, deliver to connected clients if they are recipients.

#### e. File Transfer API

- Implement HTTP endpoints for file upload (`/api/upload`) and file retrieval (dynamic URLs).
- Handle file storage securely and manage file URLs.

### Step 5: Implement the Client Application (`client/client.py`)

#### a. WebSocket Client

- Establish a WebSocket connection to the server.
- Send a `hello` message upon connection to register the public key.

#### b. Message Handling

- Implement `send_chat_message` to construct and send encrypted messages.
- Implement `send_public_chat` for plaintext messages.
- Handle incoming messages, verify signatures, and decrypt if necessary.
- Manage the `counter` to prevent replay attacks.

#### c. Frontend Integration

- Serve the HTML interface using `Flask` or similar.
- Use AJAX or WebSocket connections to send/receive messages without refreshing the page.

### Step 6: Implement the Frontend (`client/templates/index.html`)

- Create a simple HTML page with:
  - An input field for messages.
  - A send button.
  - A display area for chat messages.
  - A list of online clients.
  - Buttons or inputs to select recipients for private messages.

### Step 7: Testing and Validation

- Test client-server connections.
- Ensure messages are correctly signed, verified, encrypted, and decrypted.
- Validate that the `counter` is managed properly.
- Test file uploads and downloads.

---

## Classes and Functions Overview

### Common Module

#### `MessageType` (Enum)

- `SIGNED_DATA`
- `CLIENT_LIST_REQUEST`
- `CLIENT_UPDATE`
- `CLIENT_LIST`
- `CLIENT_UPDATE_REQUEST`
- `SERVER_HELLO`
- `HELLO`
- `CHAT`
- `PUBLIC_CHAT`

#### `protocol.py`

- `build_signed_message(data_dict, private_key, counter)`
- `verify_signed_message(message_dict, public_key, expected_counter)`

#### `crypto.py`

- `generate_rsa_key_pair()`
- `load_public_key(pem_data)`
- `load_private_key(pem_data)`
- `sign_data(data_bytes, private_key)`
- `verify_signature(data_bytes, signature_bytes, public_key)`
- `encrypt_rsa_oaep(data_bytes, public_key)`
- `decrypt_rsa_oaep(cipher_bytes, private_key)`
- `encrypt_aes_gcm(plaintext_bytes, key_bytes, iv_bytes)`
- `decrypt_aes_gcm(cipher_bytes, key_bytes, iv_bytes)`
- `calculate_fingerprint(public_key)`

### Server Module

#### `Server` Class

- **Attributes**:
  - `address`
  - `neighbour_addresses`
  - `clients`
  - `servers`
  - `client_counters`
  - `client_public_keys`
- **Methods**:
  - `start()`
  - `handle_client_connection(websocket, path)`
  - `handle_server_connection(websocket, path)`
  - `connect_to_neighbours()`
  - `broadcast_client_update()`
  - `handle_client_message(websocket, message)`
  - `handle_server_message(websocket, message)`
  - `handle_file_upload(request)`
  - `handle_file_download(request)`

### Client Module

#### `Client` Class

- **Attributes**:
  - `server_address`
  - `websocket`
  - `private_key`
  - `public_key`
  - `counter`
  - `known_clients`
- **Methods**:
  - `start()`
  - `connect_to_server()`
  - `send_hello()`
  - `send_chat_message(recipients, message_text)`
  - `send_public_chat(message_text)`
  - `request_client_list()`
  - `receive_messages()`
  - `handle_incoming_message(message)`
  - `encrypt_message(message_text, recipient_public_keys)`
  - `decrypt_message(encrypted_message, symm_key, iv)`

---

## Additional Notes

- **Message Counters**: Implement logic to track message counters for each client to prevent replay attacks. Store the last counter value for each client and validate incoming messages.

- **Error Handling**: Implement robust error handling for network issues, malformed messages, and encryption errors.

- **Security Considerations**:

  - **Key Storage**: Securely store private keys, possibly in encrypted form or in memory only.
  - **Input Validation**: Sanitize all inputs to prevent injection attacks.
  - **SSL/TLS**: Consider running the WebSocket server over TLS for an additional layer of security.

- **Frontend Simplicity**: Keep the HTML interface minimal, focusing on functionality over aesthetics.

---

## Example Flow

### Client Startup

1. Client generates or loads RSA key pair.
2. Client connects to server via WebSocket.
3. Client sends `hello` message with public key.
4. Client starts listening for incoming messages.

### Sending a Chat Message

1. User selects recipients from the online clients list.
2. User composes a message and submits it.
3. Client encrypts the message using AES-GCM with a random key and IV.
4. AES key is encrypted separately for each recipient using their public RSA keys.
5. Client constructs a `chat` message with encrypted data and sends it to the server.

### Receiving a Chat Message

1. Client receives a message from the server.
2. Client verifies the message signature and counter.
3. Client attempts to decrypt the `symm_key` using its private RSA key.
4. If successful, client decrypts the message using the AES key and IV.
5. Message is displayed to the user.
