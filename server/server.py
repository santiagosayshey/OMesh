import asyncio
import json
import websockets
from aiohttp import web
import base64
import os
import ssl
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Disable lower-level logs
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

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
    export_public_key,
    calculate_fingerprint,
    generate_rsa_key_pair,
    load_private_key,
    export_private_key
)

# Read environment variables
SERVER_ADDRESS = os.environ.get('SERVER_ADDRESS', '0.0.0.0')
SERVER_PORT = int(os.environ.get('SERVER_PORT', 8765))           # Client WS port
SERVER_SERVER_PORT = int(os.environ.get('SERVER_SERVER_PORT', 8766)) # Server WS port
HTTP_PORT = int(os.environ.get('HTTP_PORT', 8081))
PUBLIC_HOST = os.environ.get('PUBLIC_HOST', 'localhost')

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
CONFIG_DIR = 'config'
NEIGHBOURS_DIR = 'neighbours'

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

        # Generate public/private key pair and write public key to 'neighbours' directory
        self.private_key, self.public_key = self.load_or_generate_keys()

        # Ensure directories exist
        os.makedirs(CLIENTS_DIR, exist_ok=True)
        os.makedirs(FILES_DIR, exist_ok=True)
        os.makedirs(CONFIG_DIR, exist_ok=True)
        os.makedirs(NEIGHBOURS_DIR, exist_ok=True)  # Ensure the 'neighbours' directory exists

        # Write the public key to the 'neighbours' directory
        self.write_public_key_to_neighbours()

        # Initialize counters for servers
        self.server_counters = {}
        self.counter = 0  # Initialize server's own counter

        # Initialize the event loop
        self.loop = asyncio.get_event_loop()

    def load_or_generate_keys(self):
        private_key_path = os.path.join(CONFIG_DIR, 'server_private_key.pem')
        public_key_path = os.path.join(CONFIG_DIR, 'server_public_key.pem')

        if os.path.exists(private_key_path) and os.path.exists(public_key_path):
            with open(private_key_path, 'rb') as f:
                private_pem = f.read()
            with open(public_key_path, 'rb') as f:
                public_pem = f.read()
            private_key = load_private_key(private_pem)
            public_key = load_public_key(public_pem)
            logger.info("Loaded existing key pair from config directory.")
        else:
            private_key, public_key = generate_rsa_key_pair()
            private_pem = export_private_key(private_key)
            with open(private_key_path, 'wb') as f:
                f.write(private_pem)
            public_pem = export_public_key(public_key)
            with open(public_key_path, 'wb') as f:
                f.write(public_pem)
            logger.info("Generated new key pair and saved to config directory.")

        return private_key, public_key

    def write_public_key_to_neighbours(self):
        public_pem = export_public_key(self.public_key)
        neighbours_dir = NEIGHBOURS_DIR
        os.makedirs(neighbours_dir, exist_ok=True)
        key_filename = f'{self.address}_{self.server_ws_port}_public_key.pem'
        key_filepath = os.path.join(neighbours_dir, key_filename)
        with open(key_filepath, 'wb') as f:
            f.write(public_pem)
        logger.info(f"Written public key to neighbours directory: {key_filepath}")

    def load_neighbour_public_keys(self):
        """
        Loads the public keys of neighbour servers from files.
        The files should be named as '<address>_<port>_public_key.pem' and stored in 'neighbours' directory.
        """
        neighbour_public_keys = {}
        neighbours_dir = NEIGHBOURS_DIR
        os.makedirs(neighbours_dir, exist_ok=True)  # Ensure the directory exists

        for address, port in self.neighbour_addresses:
            key_filename = f'{address}_{port}_public_key.pem'
            key_filepath = os.path.join(neighbours_dir, key_filename)
            if os.path.exists(key_filepath):
                with open(key_filepath, 'rb') as f:
                    public_pem = f.read()
                public_key = load_public_key(public_pem)
                neighbour_public_keys[(address, port)] = public_key
                logger.info(f"Loaded public key for neighbour {address}:{port} from file.")
            else:
                logger.warning(f"Public key for neighbour {address}:{port} not found at {key_filepath}.")
        return neighbour_public_keys

    async def start(self):
        # Introduce a delay to allow other servers to write their public keys
        await asyncio.sleep(5)  # Wait for 5 seconds (adjust as needed)

        # Now load neighbor public keys
        self.neighbour_public_keys = self.load_neighbour_public_keys()

        # Start WebSocket server for clients
        client_server = await websockets.serve(
            self.handle_client_connection, self.address, self.client_ws_port, ping_interval=5, ssl=None
        )
        # Start WebSocket server for other servers
        server_server = await websockets.serve(
            self.handle_server_connection, self.address, self.server_ws_port, ssl=None
        )

        # Start HTTP server for file transfers
        app = web.Application()
        app.router.add_post('/api/upload', self.handle_file_upload)
        app.router.add_get('/files/{filename}', self.handle_file_download)
        app.router.add_get('/files', self.handle_file_list)
        app.router.add_get('/', self.handle_root)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.http_port)
        # Initialize the server's start time
        self.start_time = None
        await site.start()

        # Start connecting to neighbours
        asyncio.ensure_future(self.connect_to_neighbours())

        # Servers are running now; we need to keep the program running
        # Wait forever
        await asyncio.Future()

    async def connect_to_neighbours(self):
        logger.info("===== Starting connect_to_neighbours =====")
        await asyncio.sleep(1)  # Wait to ensure servers are up
        for address, port in self.neighbour_addresses:
            try:
                uri = f"wss://{address}:{port}"
                logger.info(f"Attempting to connect to server at {address}:{port}")

                # Create an SSL context that does NOT verify certificates
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False  # Disable hostname checking
                ssl_context.verify_mode = ssl.CERT_NONE  # Disable certificate verification

                # Connect to the neighbour server with the modified SSL context
                websocket = await websockets.connect(uri, ssl=ssl_context)
                self.servers[address] = websocket
                self.websocket_to_server[websocket] = address
                logger.info(f"Connected to server at {address}:{port}")

                # Send 'server_hello' with signature and counter
                self.counter += 1  # Increment server's own counter
                server_uri = f"wss://{self.address}:{self.server_ws_port}"
                server_hello_message = build_server_hello(server_uri, self.private_key, self.counter)
                server_hello_json = json.dumps(server_hello_message)
                logger.info(f"Sending 'server_hello' to server at {address}:{port}")
                await websocket.send(server_hello_json)
                logger.info(f"Sent 'server_hello' to server at {address}:{port}")

                # Request client updates
                client_update_request = build_client_update_request()
                client_update_request_json = json.dumps(client_update_request)
                logger.info(f"Requesting client updates from server at {address}:{port}")
                await websocket.send(client_update_request_json)
                logger.info(f"Requested client updates from server at {address}:{port}")

                # Start listening to this server
                logger.info(f"Starting to listen to server at {address}:{port}")
                asyncio.ensure_future(self.listen_to_server(websocket))
            except Exception as e:
                logger.error(f"Failed to connect to server at {address}:{port}: {e}")
        logger.info("===== Finished connect_to_neighbours =====")

    def get_neighbour_public_key(self, sender_address):
        """
        Retrieves the public key of a neighbour server based on the sender's address.
        If not found in memory, attempts to load it from the 'neighbours' directory.
        """
        # Strip 'wss://' prefix if present
        if sender_address.startswith('wss://'):
            sender_address = sender_address[6:]

        # Remove port if present
        if ':' in sender_address:
            address_only = sender_address.split(':')[0]
        else:
            address_only = sender_address

        # Check if the public key is already loaded
        for (address, port), public_key in self.neighbour_public_keys.items():
            if sender_address == address or address_only == address:
                return public_key

        # Attempt to load the public key from the 'neighbours' directory
        for address, port in self.neighbour_addresses:
            if sender_address == address or address_only == address:
                key_filename = f'{address}_{port}_public_key.pem'
                key_filepath = os.path.join(NEIGHBOURS_DIR, key_filename)
                if os.path.exists(key_filepath):
                    with open(key_filepath, 'rb') as f:
                        public_pem = f.read()
                    public_key = load_public_key(public_pem)
                    self.neighbour_public_keys[(address, port)] = public_key
                    logger.info(f"Loaded public key for neighbour {address}:{port} from file.")
                    return public_key
                else:
                    logger.warning(f"Public key for neighbour {address}:{port} not found at {key_filepath}.")
                    return None
        return None

    async def handle_client_connection(self, websocket, path):
        client_ip, client_port = websocket.remote_address
        print(f"New client connected from {client_ip}:{client_port}")
        fingerprint = None
        try:
            async for message in websocket:
                message_dict, error = parse_message(message)
                if error:
                    logger.error(f"Error parsing message from client: {error}")
                    logger.error(f"Erroneous message: {message}")
                    continue

                # Log the received message type
                log_message("Received", message)

                # Handle client messages
                await self.handle_client_message(websocket, message_dict, fingerprint)

                # If we have received the 'hello' message, store the client's fingerprint
                if fingerprint is None and message_dict.get('type') == MessageType.SIGNED_DATA.value:
                    if message_dict["data"].get("type") == 'hello':
                        public_key_pem_str = message_dict['data']['public_key']
                        public_key_pem = public_key_pem_str.encode('utf-8')
                        public_key = load_public_key(public_key_pem)
                        fingerprint = calculate_fingerprint(public_key)
                        self.clients[fingerprint] = websocket
                        self.client_public_keys[fingerprint] = public_key
                        self.client_counters[fingerprint] = 0  # Initialize counter
                        self.fingerprint_to_server[fingerprint] = self.address  # Associate client with this server
                        logger.info(f"Registered new client with fingerprint: {fingerprint} from {client_ip}:{client_port}")

                        # Broadcast the updated client list to other servers
                        await self.broadcast_client_update()
        except Exception as e:
            # Log more detailed information on disconnection
            logger.error(f"Exception in handle_client_connection: {e}")
            if fingerprint:
                logger.info(f"Client {fingerprint} disconnected from {client_ip}:{client_port}. Exception: {e}")
            else:
                logger.info(f"Unknown client disconnected from {client_ip}:{client_port}. Exception: {e}")
        finally:
            logger.info(f"Executing finally block for client from {client_ip}:{client_port}")
            # Clean up on disconnection
            if fingerprint:
                self.clients.pop(fingerprint, None)
                self.client_public_keys.pop(fingerprint, None)
                self.client_counters.pop(fingerprint, None)
                self.fingerprint_to_server.pop(fingerprint, None)
                logger.info(f"Cleaned up data for client {fingerprint}.")
            else:
                logger.info(f"No fingerprint available for client from {client_ip}:{client_port}. No cleanup performed.")

            # Broadcast the updated client list to other servers
            await self.broadcast_client_update()

    async def handle_server_connection(self, websocket, path):
        print("New server connected")
        try:
            async for message in websocket:
                message_dict, error = parse_message(message)
                if error:
                    logger.error(f"Error parsing message from server: {error}")
                    logger.error(f"Erroneous message: {message}")
                    continue

                # Log the received message type
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

    async def listen_to_server(self, websocket):
        try:
            async for message in websocket:
                message_dict, error = parse_message(message)
                if error:
                    logger.error(f"Error parsing message from server: {error}")
                    logger.error(f"Erroneous message: {message}")
                    continue

                # Log the received message type
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
        
        # Log the message body
        logger.info(f"Client update message body: {message_json}")

        for server_address, websocket in self.servers.items():
            try:
                await websocket.send(message_json)
                logger.info(f"Sent client update to server {server_address}.")
            except Exception as e:
                logger.error(f"Error sending client update to server {server_address}: {e}")

    async def handle_client_message(self, websocket, message_dict, client_fingerprint):
        # First, verify the message structure
        if not validate_message_format(message_dict):
            logger.error("Invalid message format from client")
            logger.error(f"Erroneous message: {message_dict}")
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
                    logger.error("Unknown sender fingerprint")
                    return
                is_valid, error = verify_signed_message(message_dict, public_key, self.client_counters.get(sender_fingerprint, 0))
                if not is_valid:
                    logger.error(f"Invalid signed message from client: {error}")
                    logger.error(f"Erroneous message: {message_dict}")
                    return
                # Update counter
                counter = message_dict["counter"]
                self.client_counters[sender_fingerprint] = counter

                # Handle the message based on its type
                if data_type == 'chat':
                    await self.forward_message(message_dict)
                elif data_type == 'public_chat':
                    await self.handle_public_chat(message_dict, from_client=True)
            else:
                logger.warning(f"Unknown data type in signed_data message: {data_type}")

        elif message_type == MessageType.CLIENT_LIST_REQUEST.value:
            logger.info("Received 'client_list_request' from client")
            await self.send_client_list(websocket)

        else:
            logger.warning(f"Unknown message type from client: {message_type}")

    async def handle_server_message(self, websocket, message_dict):
        # Validate the message structure
        if not validate_message_format(message_dict):
            logger.error("Invalid message format from server")
            logger.error(f"Erroneous message: {message_dict}")
            return

        # Check if the message is of type 'signed_data'
        if message_dict.get("type") == MessageType.SIGNED_DATA.value:
            # Extract the signed data
            data_dict = message_dict.get("data", {})
            data_type = data_dict.get("type")

            # For 'server_hello' messages, verify the signature
            if data_type == MessageType.SERVER_HELLO.value:
                sender_address = data_dict.get("sender")
                if not sender_address:
                    logger.error("Missing sender address in 'server_hello' message")
                    return

                # Get the public key of the sender
                public_key = self.get_neighbour_public_key(sender_address)
                if not public_key:
                    logger.error(f"Unknown sender {sender_address}, cannot verify signature")
                    return

                # Get the last counter for this sender
                counter = message_dict.get("counter")
                last_counter = self.server_counters.get(sender_address, 0)

                # Verify the signature
                is_valid, error = verify_signed_message(message_dict, public_key, last_counter)
                if not is_valid:
                    logger.error(f"Invalid signed 'server_hello' message from {sender_address}: {error}")
                    logger.error(f"Erroneous message: {message_dict}")
                    return

                # Update the counter
                self.server_counters[sender_address] = counter

                # Map the websocket to the sender_address
                self.websocket_to_server[websocket] = sender_address
                self.servers[sender_address] = websocket  # Update the servers dict
                logger.info(f"Mapped websocket to server {sender_address}.")

            else:
                # For other signed_data messages from clients, do not verify signature
                if data_type == MessageType.CHAT.value:
                    await self.forward_message(message_dict)
                elif data_type == MessageType.PUBLIC_CHAT.value:
                    # For public chat from other servers, deliver to clients only
                    await self.handle_public_chat(message_dict, from_client=False)
                else:
                    logger.warning(f"Received unexpected signed data type from server: {data_type}")

        else:
            # Non-signed messages
            message_type = message_dict.get("type")

            if message_type == MessageType.CLIENT_UPDATE.value:
                # Handle 'client_update'
                clients_pem = message_dict.get('clients', [])

                # Identify the server address from which this message was received
                server_address = self.websocket_to_server.get(websocket)

                if not server_address:
                    logger.warning("Received 'client_update' from an unknown server.")
                    return

                for public_key_pem_str in clients_pem:
                    public_key_pem = public_key_pem_str.encode('utf-8')
                    public_key = load_public_key(public_key_pem)
                    fingerprint = calculate_fingerprint(public_key)
                    self.client_public_keys[fingerprint] = public_key

                    # Update the fingerprint-to-server mapping
                    self.fingerprint_to_server[fingerprint] = server_address
                    logger.info(f"Client {fingerprint} is associated with server {server_address}.")

                logger.info(f"Updated client list from server {server_address}.")

            elif message_type == MessageType.CLIENT_UPDATE_REQUEST.value:
                # Handle 'client_update_request'
                logger.info("Received 'client_update_request' from server.")
                await self.broadcast_client_update()

            elif message_type == MessageType.SERVER_HELLO.value:
                # Handle unsigned 'server_hello' (for backward compatibility)
                sender_address = message_dict.get("sender")
                if not sender_address:
                    logger.error("Missing sender address in 'server_hello' message")
                    return

                # Map the websocket to the sender_address
                self.websocket_to_server[websocket] = sender_address
                self.servers[sender_address] = websocket  # Update the servers dict
                logger.info(f"Mapped websocket to server {sender_address}.")

            else:
                logger.warning(f"Unknown message type from server: {message_type}")

    async def forward_message(self, message_dict):
        data = message_dict.get('data', {})
        message_type = data.get('type')

        if message_type == 'chat':
            destination_servers = data.get('destination_servers', [])

            # Deliver to clients on this server if it's a destination
            if self.address in destination_servers:
                await self.deliver_message_to_clients(message_dict)

            # Forward to other servers, but only the part they need
            for server_address in destination_servers:
                if server_address != self.address and server_address in self.servers:
                    websocket = self.servers[server_address]
                    try:
                        # Create a new message with only this server as destination
                        server_specific_message = message_dict.copy()
                        server_specific_message['data'] = data.copy()
                        server_specific_message['data']['destination_servers'] = [server_address]

                        # Send the server-specific message
                        await websocket.send(json.dumps(server_specific_message))
                        logger.info(f"Forwarded chat message to server {server_address}.")
                    except Exception as e:
                        logger.error(f"Error forwarding message to server {server_address}: {e}")

        else:
            logger.warning(f"Unknown message type: {message_type}")

    async def deliver_message_to_clients(self, message_dict):
        message_json = json.dumps(message_dict)
        for fingerprint, websocket in self.clients.items():
            try:
                await websocket.send(message_json)
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
                public_key_pem_str = export_public_key(public_key).decode('utf-8')
                servers_dict[server_address].append(public_key_pem_str)

        # Convert the grouped dictionary to the required format
        servers = []
        for address, clients in servers_dict.items():
            servers.append({
                "address": address,
                "clients": clients
            })

        client_list_message = {
            "type": "client_list",
            "servers": servers
        }
        message_json = json.dumps(client_list_message)

        try:
            await websocket.send(message_json)
            logger.info("Sent 'client_list' response to client.")
        except Exception as e:
            logger.error(f"Error sending client list to client: {e}")

    async def handle_public_chat(self, message_dict, from_client):
        # Deliver to all clients on this server
        await self.deliver_message_to_clients(message_dict)

        if from_client:
            # Forward to all other servers
            message_json = json.dumps(message_dict)
            for server_address, websocket in self.servers.items():
                if server_address != self.address:
                    try:
                        await websocket.send(message_json)
                        logger.info(f"Forwarded public chat to server {server_address}.")
                    except Exception as e:
                        logger.error(f"Error forwarding public chat to server {server_address}: {e}")

    async def handle_file_upload(self, request):
        reader = await request.multipart()
        field = await reader.next()
        if not field or field.name != 'file':
            return web.json_response({'error': 'No file field in request'}, status=400)
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
                    return web.json_response({'error': 'File size exceeds limit'}, status=413)
                f.write(chunk)

        file_url = f"http://{PUBLIC_HOST}:{self.http_port}/files/{filename}"
        return web.json_response({'file_url': file_url})

    async def handle_file_download(self, request):
        filename = request.match_info['filename']
        filepath = os.path.join(FILES_DIR, filename)
        if not os.path.exists(filepath):
            return web.HTTPNotFound()
        return web.FileResponse(filepath)
    
    async def handle_file_list(self, request):
        files = os.listdir(FILES_DIR)
        files.sort()  # Optionally sort the file list

        # Build an HTML response
        html = "<html><body><h1>Uploaded Files</h1><ul>"
        for filename in files:
            file_url = f"/files/{filename}"
            html += f'<li><a href="{file_url}">{filename}</a></li>'
        html += "</ul></body></html>"

        return web.Response(text=html, content_type='text/html')
    
    async def handle_root(self, request):
        # Return a funny message
        return web.Response(text="What are you doing here? 🤔")

def log_message(direction, message):
    if direction == "Received":
        try:
            parsed_message = json.loads(message)
            message_type = parsed_message.get("type", "Unknown")
            if message_type == MessageType.SIGNED_DATA.value:
                data_type = parsed_message.get("data", {}).get("type", "Unknown")
                logger.info(f"Received message of type '{data_type}'")
            else:
                logger.info(f"Received message of type '{message_type}'")
        except json.JSONDecodeError:
            logger.info("Received non-JSON message")

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
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("Server shutting down")
