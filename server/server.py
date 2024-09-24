# server/server.py

import asyncio
import json
import websockets
from aiohttp import web
import base64
import os

import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Disable lower-level logs
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

# Enable detailed message logging based on the LOG_MESSAGES environment variable
LOG_MESSAGES = os.environ.get('LOG_MESSAGES', 'False').lower() in ('true', '1', 't')

from common.protocol import (
    parse_message,
    validate_message_format,
    build_signed_message,
    verify_signed_message,
    build_client_update,
    build_client_update_request,
    build_server_hello,
    MessageType
)
from common.crypto import (
    load_public_key,
    load_private_key,
    export_public_key,
    export_private_key,
    calculate_fingerprint,
)

# Read environment variables
SERVER_ADDRESS = os.environ.get('SERVER_ADDRESS', '0.0.0.0')
SERVER_PORT = int(os.environ.get('SERVER_PORT', 8765))           # Client WS port
SERVER_SERVER_PORT = int(os.environ.get('SERVER_SERVER_PORT', 8766)) # Server WS port
HTTP_PORT = int(os.environ.get('HTTP_PORT', 8081))

# Parse NEIGHBOUR_ADDRESSES environment variable
neighbour_addresses_env = os.environ.get('NEIGHBOUR_ADDRESSES', '')
NEIGHBOUR_ADDRESSES = []
if neighbour_addresses_env:
    for addr in neighbour_addresses_env.split(','):
        if ':' in addr:
            host, port = addr.split(':')
            NEIGHBOUR_ADDRESSES.append((host.strip(), int(port.strip())))
        else:
            NEIGHBOUR_ADDRESSES.append((addr.strip(), SERVER_SERVER_PORT))  # Default to SERVER_SERVER_PORT if port not specified

# Paths for storing client public keys and uploaded files
CLIENTS_DIR = 'clients'
FILES_DIR = 'files'

class Server:
    def __init__(self, address, client_ws_port, server_ws_port, http_port, neighbours):
        self.address = address
        self.client_ws_port = client_ws_port
        self.server_ws_port = server_ws_port
        self.http_port = http_port
        self.neighbour_addresses = neighbours  # List of (address, port) tuples

        # Client-related data structures
        self.clients = {}  # {fingerprint: websocket}
        self.client_public_keys = {}  # {fingerprint: public_key}
        self.client_counters = {}  # {fingerprint: last_counter}

        # Server-related data structures
        self.servers = {}  # {address: websocket}
        self.websocket_to_server = {}  # {websocket: address}

        # Mapping of client fingerprints to their respective servers
        self.fingerprint_to_server = {}  # {fingerprint: server_address}

        # Initialize the event loop
        self.loop = asyncio.get_event_loop()

        # Ensure directories exist
        os.makedirs(CLIENTS_DIR, exist_ok=True)
        os.makedirs(FILES_DIR, exist_ok=True)


    async def start(self):
        # Start WebSocket server for clients
        client_server = websockets.serve(
            self.handle_client_connection, self.address, self.client_ws_port, ping_interval=None
        )
        # Start WebSocket server for other servers
        server_server = websockets.serve(
            self.handle_server_connection, self.address, self.server_ws_port, ping_interval=None
        )

        # Start HTTP server for file transfers
        app = web.Application()
        app.router.add_post('/api/upload', self.handle_file_upload)
        app.router.add_get('/files/{filename}', self.handle_file_download)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.address, self.http_port)

        # Run all servers and connect to neighbours concurrently
        await asyncio.gather(
            client_server,
            server_server,
            site.start(),
            self.connect_to_neighbours(),
        )

    async def handle_client_connection(self, websocket, path):
        print("New client connected")
        fingerprint = None
        try:
            async for message in websocket:
                message_dict, error = parse_message(message)
                if error:
                    print(f"Error parsing message from client: {error}")
                    continue

                # Log the received message without sensitive fields
                log_message("Received", message)

                # Handle client messages
                await self.handle_client_message(websocket, message_dict, fingerprint)

                # If we have received the 'hello' message, store the client's fingerprint
                if fingerprint is None and message_dict.get('type') == MessageType.SIGNED_DATA.value:
                    if message_dict["data"].get("type") == 'hello':
                        public_key_b64 = message_dict['data']['public_key']
                        public_key_pem = base64.b64decode(public_key_b64.encode('utf-8'))
                        public_key = load_public_key(public_key_pem)
                        fingerprint = calculate_fingerprint(public_key)
                        self.clients[fingerprint] = websocket
                        self.client_public_keys[fingerprint] = public_key
                        self.client_counters[fingerprint] = 0  # Initialize counter
                        self.fingerprint_to_server[fingerprint] = self.address  # Associate client with this server
                        logger.info(f"Registered new client with fingerprint: {fingerprint}")

                        # Broadcast the updated client list to other servers
                        await self.broadcast_client_update()
        except websockets.ConnectionClosed:
            print("Client disconnected")
        finally:
            # Clean up on disconnection
            if fingerprint:
                self.clients.pop(fingerprint, None)
                self.client_public_keys.pop(fingerprint, None)
                self.client_counters.pop(fingerprint, None)
                self.fingerprint_to_server.pop(fingerprint, None)
                logger.info(f"Client {fingerprint} disconnected.")

                # Broadcast the updated client list to other servers
                await self.broadcast_client_update()

    async def handle_server_connection(self, websocket, path):
        print("New server connected")
        try:
            async for message in websocket:
                message_dict, error = parse_message(message)
                if error:
                    print(f"Error parsing message from server: {error}")
                    continue

                # Log the received message without sensitive fields
                log_message("Received", message)

                # Handle server messages
                await self.handle_server_message(websocket, message_dict)
        except websockets.ConnectionClosed:
            print("Server disconnected")
        finally:
            # Remove server from mappings
            server_address = self.websocket_to_server.get(websocket)
            if server_address:
                del self.servers[server_address]
                del self.websocket_to_server[websocket]
                logger.info(f"Disconnected from server {server_address}.")

    async def connect_to_neighbours(self):
        await asyncio.sleep(1)  # Wait to ensure servers are up
        for address, port in self.neighbour_addresses:
            try:
                # Connect to the neighbor's server WebSocket port
                neighbor_server_ws_port = port  # Ensure 'port' here refers to server_ws_port of the neighbor
                uri = f"ws://{address}:{neighbor_server_ws_port}"
                websocket = await websockets.connect(uri)
                self.servers[address] = websocket
                self.websocket_to_server[websocket] = address  # Initially map websocket to address
                logger.info(f"Connected to server at {address}:{neighbor_server_ws_port}")

                # Send 'server_hello'
                server_hello_message = build_server_hello(self.address)
                server_hello_json = json.dumps(server_hello_message)
                await websocket.send(server_hello_json)
                log_message("Sent", server_hello_json)

                # Request client updates
                client_update_request = build_client_update_request()
                client_update_request_json = json.dumps(client_update_request)
                await websocket.send(client_update_request_json)
                log_message("Sent", client_update_request_json)

                # Start listening to this server
                asyncio.ensure_future(self.listen_to_server(websocket))
            except Exception as e:
                logger.error(f"Failed to connect to server at {address}:{port}: {e}")

    async def listen_to_server(self, websocket):
        try:
            async for message in websocket:
                message_dict, error = parse_message(message)
                if error:
                    print(f"Error parsing message from server: {error}")
                    continue

                # Log the received message without sensitive fields
                log_message("Received", message)

                # Handle server messages
                await self.handle_server_message(websocket, message_dict)
        except websockets.ConnectionClosed:
            print("Server connection closed")
        finally:
            # Remove server from mappings
            server_address = self.websocket_to_server.get(websocket)
            if server_address:
                del self.servers[server_address]
                del self.websocket_to_server[websocket]
                logger.info(f"Disconnected from server {server_address}.")

    async def broadcast_client_update(self):
        """
        Broadcasts the current client list to all connected servers.
        Each server will receive only the clients connected to this server.
        """
        # Prepare client_update message with only the clients connected to this server
        clients_public_keys = [
            public_key for fingerprint, public_key in self.client_public_keys.items()
            if self.fingerprint_to_server.get(fingerprint) == self.address
        ]
        client_update_message = build_client_update(clients_public_keys)
        message_json = json.dumps(client_update_message)

        for server_address, websocket in self.servers.items():
            try:
                await websocket.send(message_json)
                log_message("Sent", message_json)
                logger.info(f"Sent client update to server {server_address}.")
            except Exception as e:
                logger.error(f"Error sending client update to server {server_address}: {e}")

    async def handle_client_message(self, websocket, message_dict, client_fingerprint):
        # First, verify the message structure
        if not validate_message_format(message_dict):
            print("Invalid message format")
            return

        message_type = message_dict.get("type")

        if message_type == MessageType.SIGNED_DATA.value:
            data_type = message_dict["data"].get("type")
            if data_type == 'hello':
                # 'hello' message is handled in handle_client_connection
                return
            elif data_type in ['chat', 'public_chat']:
                # Verify signature and handle chat messages
                sender_fingerprint = client_fingerprint
                public_key = self.client_public_keys.get(sender_fingerprint)
                if not public_key:
                    print("Unknown sender fingerprint")
                    return
                is_valid, error = verify_signed_message(message_dict, public_key, self.client_counters.get(sender_fingerprint, 0))
                if not is_valid:
                    print(f"Invalid signed message: {error}")
                    return
                # Update counter
                counter = message_dict["counter"]
                self.client_counters[sender_fingerprint] = counter

                # Forward the message
                await self.forward_message(message_dict)
            else:
                print(f"Unknown data type in signed_data message: {data_type}")

        elif message_type == MessageType.CLIENT_LIST_REQUEST.value:
            logger.info("Received 'client_list_request' from client")
            await self.send_client_list(websocket)

        else:
            print(f"Unknown message type: {message_type}")

    async def handle_server_message(self, websocket, message_dict):
        # Validate the message structure
        if not validate_message_format(message_dict):
            print("Invalid message format from server")
            return

        # Determine if 'type' is within 'data' or at the top level
        if "data" in message_dict and "type" in message_dict["data"]:
            # Extract 'type' from within 'data'
            data = message_dict.get("data", {})
            message_type = data.get("type")
        else:
            # Extract 'type' from the top level
            message_type = message_dict.get("type")

        if message_type == MessageType.CLIENT_UPDATE.value:
            # Handle client_update
            clients_b64 = message_dict.get('clients', [])

            # Identify the server address from which this message was received
            server_address = self.websocket_to_server.get(websocket)

            if not server_address:
                logger.warning("Received client_update from an unknown server.")
                return

            for public_key_b64 in clients_b64:
                public_key_pem = base64.b64decode(public_key_b64.encode('utf-8'))
                public_key = load_public_key(public_key_pem)
                fingerprint = calculate_fingerprint(public_key)
                self.client_public_keys[fingerprint] = public_key
                
                # Only update the fingerprint_to_server mapping if it doesn't exist
                # or if the existing mapping is for the current server
                if fingerprint not in self.fingerprint_to_server or self.fingerprint_to_server[fingerprint] == self.address:
                    self.fingerprint_to_server[fingerprint] = server_address
                    logger.info(f"Client {fingerprint} is associated with server {server_address}.")

            logger.info(f"Updated client list from server {server_address}.")

        elif message_type == MessageType.CLIENT_UPDATE_REQUEST.value:
            # Handle client_update_request
            logger.info("Received 'client_update_request' from server.")
            await self.broadcast_client_update()

        elif message_type == MessageType.SERVER_HELLO.value:
            # Handle server_hello
            sender_address = message_dict["data"].get("sender")
            logger.info(f"Received 'server_hello' from {sender_address}")

            # Map the websocket to the sender_address
            self.websocket_to_server[websocket] = sender_address
            self.servers[sender_address] = websocket  # Update the servers dict
            logger.info(f"Mapped websocket to server {sender_address}.")

            # Optionally, send a client_update_request if not already sent
            # await self.broadcast_client_update()

        elif message_type in [MessageType.CHAT.value, MessageType.PUBLIC_CHAT.value]:
            # Handle chat messages
            await self.forward_message(message_dict)

        else:
            print(f"Unknown message type from server: {message_type}")

    async def forward_message(self, message_dict):
        data = message_dict.get('data', {})
        message_type = data.get('type')
        message_json = json.dumps(message_dict)

        if message_type == 'chat':
            destination_servers = data.get('destination_servers', [])
            if not destination_servers:
                logger.error("No destination servers specified in chat message.")
                return

            logger.info(f"Forwarding message to servers: {destination_servers}")

            for server_address in destination_servers:
                if server_address == self.address:
                    await self.deliver_message_to_clients(message_dict)
                elif server_address in self.servers:
                    websocket = self.servers[server_address]
                    try:
                        await websocket.send(message_json)
                        log_message("Forwarded", message_json)
                        logger.info(f"Forwarded chat message to server {server_address}.")
                    except Exception as e:
                        logger.error(f"Error forwarding message to server {server_address}: {e}")
                else:
                    logger.error(f"Destination server {server_address} not found in known servers.")

        elif message_type == 'public_chat':
            # Broadcast public chat to all clients and servers
            await self.deliver_message_to_clients(message_dict)
            for server_address, websocket in self.servers.items():
                try:
                    await websocket.send(message_json)
                    log_message("Sent", message_json)
                    logger.info(f"Broadcasted public chat to server {server_address}.")
                except Exception as e:
                    logger.error(f"Error forwarding public chat to server {server_address}: {e}")
        else:
            print(f"Unknown message type: {message_type}")

    async def deliver_message_to_clients(self, message_dict):
        message_json = json.dumps(message_dict)
        for fingerprint, websocket in self.clients.items():
            try:
                await websocket.send(message_json)
                log_message("Sent", message_json)
                logger.info(f"Delivered message to client {fingerprint}.")
            except Exception as e:
                logger.error(f"Error delivering message to client {fingerprint}: {e}")

    async def send_client_list(self, websocket):
        logger.info(f"Preparing client list. Known clients: {list(self.client_public_keys.keys())}")

        # Group clients by their associated servers
        servers_dict = {}
        for fingerprint, server_address in self.fingerprint_to_server.items():
            if server_address not in servers_dict:
                servers_dict[server_address] = []
            public_key = self.client_public_keys.get(fingerprint)
            if public_key:
                public_key_b64 = base64.b64encode(export_public_key(public_key)).decode('utf-8')
                servers_dict[server_address].append(public_key_b64)

        # Convert the grouped dictionary to the required format
        servers = []
        for address, clients in servers_dict.items():
            servers.append({
                "address": address,
                "clients": clients
            })

        # Include this server's own clients if not already included
        own_clients_b64 = [
            base64.b64encode(export_public_key(public_key)).decode('utf-8')
            for fingerprint, public_key in self.client_public_keys.items()
            if self.fingerprint_to_server.get(fingerprint) == self.address
        ]

        if own_clients_b64:
            # Check if this server is already in the servers list
            addresses = [server["address"] for server in servers]
            if self.address not in addresses:
                servers.append({
                    "address": self.address,
                    "clients": own_clients_b64
                })
            else:
                # Append to existing server entry
                for server in servers:
                    if server["address"] == self.address:
                        server["clients"].extend(own_clients_b64)
                        break

        client_list_message = {
            "type": "client_list",
            "servers": servers
        }
        message_json = json.dumps(client_list_message)

        try:
            await websocket.send(message_json)
            log_message("Sent", message_json)
            logger.info("Sent 'client_list' response to client.")
        except Exception as e:
            logger.error(f"Error sending client list to client: {e}")

    async def handle_file_upload(self, request):
        reader = await request.multipart()
        field = await reader.next()
        if field.name != 'file':
            return web.HTTPBadRequest(text="No file field in request")
        filename = field.filename

        # Set a maximum file size limit (e.g., 10 MB)
        max_file_size = 10 * 1024 * 1024
        size = 0

        # Save the file
        filepath = os.path.join(FILES_DIR, filename)
        with open(filepath, 'wb') as f:
            while True:
                chunk = await field.read_chunk()
                if not chunk:
                    break
                size += len(chunk)
                if size > max_file_size:
                    os.remove(filepath)
                    return web.HTTPRequestEntityTooLarge()
                f.write(chunk)

        file_url = f"http://{self.address}:{self.http_port}/files/{filename}"
        return web.json_response({'file_url': file_url})

    async def handle_file_download(self, request):
        filename = request.match_info['filename']
        filepath = os.path.join(FILES_DIR, filename)
        if not os.path.exists(filepath):
            return web.HTTPNotFound()
        return web.FileResponse(filepath)

def log_message(direction, message):
    # Always log the basic message direction
    logger.info(f"{direction} message.")

    # Conditionally log the detailed message content
    if LOG_MESSAGES:
        try:
            parsed_message = json.loads(message)
            # Remove or mask 'public_key' and 'signature' fields
            sanitized_message = sanitize_message(parsed_message)
            formatted_json = json.dumps(sanitized_message, indent=2)
            logger.info(f"{direction} message details:\n{formatted_json}")
        except json.JSONDecodeError:
            logger.info(f"{direction} message (not JSON):\n{message}")

def sanitize_message(message):
    """
    Removes or masks sensitive fields like 'public_key' and 'signature' from the message.
    """
    message_copy = json.loads(json.dumps(message))  # Deep copy
    if 'data' in message_copy:
        data = message_copy['data']
        if 'public_key' in data:
            data['public_key'] = "[OMITTED]"
    if 'signature' in message_copy:
        message_copy['signature'] = "[OMITTED]"
    return message_copy

# Entry point
if __name__ == '__main__':
    import sys

    # Read server configuration from environment variables
    address = SERVER_ADDRESS
    client_ws_port = SERVER_PORT
    server_ws_port = SERVER_SERVER_PORT
    http_port = HTTP_PORT
    neighbours = NEIGHBOUR_ADDRESSES

    # Create Server instance with correct parameters
    server = Server(address, client_ws_port, server_ws_port, http_port, neighbours)
    try:
        asyncio.get_event_loop().run_until_complete(server.start())
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        print("Server shutting down")
