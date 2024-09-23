# server/server.py

import asyncio
import json
import websockets
import aiohttp
from aiohttp import web
import base64
import os

from common.protocol import (
    parse_message,
    validate_message_format,
    build_signed_message,
    verify_signed_message,
    build_client_update,
    build_client_update_request,
    build_server_hello,
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
SERVER_PORT = int(os.environ.get('SERVER_PORT', 8765))
HTTP_PORT = int(os.environ.get('HTTP_PORT', 8081))

# Parse NEIGHBOUR_ADDRESSES environment variable
neighbour_addresses_env = os.environ.get('NEIGHBOUR_ADDRESSES', '')
NEIGHBOUR_ADDRESSES = []
if neighbour_addresses_env:
    for addr in neighbour_addresses_env.split(','):
        host, port = addr.split(':') if ':' in addr else (addr, '8765')
        NEIGHBOUR_ADDRESSES.append((host.strip(), int(port.strip())))


# Paths for storing client public keys and uploaded files
CLIENTS_DIR = 'clients'
FILES_DIR = 'files'

class Server:
    def __init__(self, address, ws_port, http_port, neighbours):
        self.address = address
        self.ws_port = ws_port
        self.http_port = http_port
        self.neighbour_addresses = neighbours  # List of (address, port) tuples
        self.clients = {}  # {fingerprint: websocket}
        self.client_public_keys = {}  # {fingerprint: public_key}
        self.client_counters = {}  # {fingerprint: last_counter}
        self.servers = {}  # {address: websocket}
        self.server_public_keys = {}  # {address: public_key}
        self.loop = asyncio.get_event_loop()

        # Ensure directories exist
        os.makedirs(CLIENTS_DIR, exist_ok=True)
        os.makedirs(FILES_DIR, exist_ok=True)

    async def start(self):
        # Start WebSocket server for clients
        client_server = websockets.serve(
            self.handle_client_connection, self.address, self.ws_port, ping_interval=None
        )
        # Start WebSocket server for other servers
        server_server = websockets.serve(
            self.handle_server_connection, self.address, self.ws_port + 1, ping_interval=None
        )

        # Start HTTP server for file transfers
        app = web.Application()
        app.router.add_post('/api/upload', self.handle_file_upload)
        app.router.add_get('/files/{filename}', self.handle_file_download)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.address, self.http_port)

        # Run servers
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

                # Handle client messages
                await self.handle_client_message(websocket, message_dict, fingerprint)

                # If we have received the 'hello' message, store the client's fingerprint
                if fingerprint is None and message_dict.get('data', {}).get('type') == 'hello':
                    public_key_b64 = message_dict['data']['public_key']
                    public_key_pem = base64.b64decode(public_key_b64.encode('utf-8'))
                    public_key = load_public_key(public_key_pem)
                    fingerprint = calculate_fingerprint(public_key)
                    self.clients[fingerprint] = websocket
                    self.client_public_keys[fingerprint] = public_key
                    self.client_counters[fingerprint] = 0  # Initialize counter
                    print(f"Client registered with fingerprint: {fingerprint}")

                    # Send client update to other servers
                    await self.broadcast_client_update()
        except websockets.ConnectionClosed:
            print("Client disconnected")
        finally:
            # Clean up on disconnection
            if fingerprint:
                self.clients.pop(fingerprint, None)
                self.client_public_keys.pop(fingerprint, None)
                self.client_counters.pop(fingerprint, None)
                # Notify other servers about client update
                await self.broadcast_client_update()

    async def handle_server_connection(self, websocket, path):
        print("New server connected")
        try:
            async for message in websocket:
                message_dict, error = parse_message(message)
                if error:
                    print(f"Error parsing message from server: {error}")
                    continue

                # Handle server messages
                await self.handle_server_message(websocket, message_dict)
        except websockets.ConnectionClosed:
            print("Server disconnected")

    async def connect_to_neighbours(self):
        await asyncio.sleep(1)  # Wait a bit to ensure servers are up
        for address, port in self.neighbour_addresses:
            try:
                uri = f"ws://{address}:{port + 1}"  # Servers connect on ws_port + 1
                websocket = await websockets.connect(uri)
                self.servers[address] = websocket
                print(f"Connected to server at {address}:{port + 1}")

                # Send 'server_hello'
                server_hello_message = build_server_hello(self.address)
                await websocket.send(json.dumps(server_hello_message))

                # Request client updates
                client_update_request = build_client_update_request()
                await websocket.send(json.dumps(client_update_request))

                # Start listening to this server
                asyncio.ensure_future(self.listen_to_server(websocket))
            except Exception as e:
                print(f"Failed to connect to server at {address}:{port + 1}: {e}")

    async def listen_to_server(self, websocket):
        try:
            async for message in websocket:
                message_dict, error = parse_message(message)
                if error:
                    print(f"Error parsing message from server: {error}")
                    continue

                # Handle server messages
                await self.handle_server_message(websocket, message_dict)
        except websockets.ConnectionClosed:
            print("Server connection closed")
        finally:
            # Remove server from list
            for address, ws in list(self.servers.items()):
                if ws == websocket:
                    del self.servers[address]
                    break

    async def broadcast_client_update(self):
        # Build client update message
        clients_public_keys = list(self.client_public_keys.values())
        client_update_message = build_client_update(clients_public_keys)
        message_json = json.dumps(client_update_message)

        # Send to all connected servers
        for websocket in self.servers.values():
            try:
                await websocket.send(message_json)
            except Exception as e:
                print(f"Error sending client update to server: {e}")

    async def handle_client_message(self, websocket, message_dict, client_fingerprint):
        # Extract message_type
        if "type" in message_dict:
            message_type = message_dict["type"]
        elif "data" in message_dict and "type" in message_dict["data"]:
            message_type = message_dict["data"]["type"]
        else:
            print("Received message without 'type'")
            return

        data = message_dict.get('data', {})
        message_type = data.get('type')

        if message_type == 'hello':
            # Handle 'hello' message
            pass  # Already handled in the connection function
        elif message_type == 'chat' or message_type == 'public_chat':
            # Forward message to destination servers or clients
            await self.forward_message(message_dict)
        elif message_type == 'client_list_request':
            # Send client list
            await self.send_client_list(websocket)
        else:
            print(f"Unknown message type from client: {message_type}")

    async def handle_server_message(self, websocket, message_dict):
        # Extract message_type
        if "type" in message_dict:
            message_type = message_dict["type"]
        elif "data" in message_dict and "type" in message_dict["data"]:
            message_type = message_dict["data"]["type"]
        else:
            print("Received message without 'type'")
            return

        if message_type == 'client_update':
            # Update internal client list
            clients_b64 = message_dict.get('clients', [])
            for public_key_b64 in clients_b64:
                public_key_pem = base64.b64decode(public_key_b64.encode('utf-8'))
                public_key = load_public_key(public_key_pem)
                fingerprint = calculate_fingerprint(public_key)
                # Assuming clients connected to other servers are not directly connected here
                self.client_public_keys[fingerprint] = public_key
                # No websocket connection for clients on other servers
        elif message_type == 'client_update_request':
            # Send client update to requesting server
            await self.broadcast_client_update()
        elif message_type == 'server_hello':
            # Handle server hello
            pass  # For now, no action needed
        elif message_type == 'chat' or message_type == 'public_chat':
            # Forward message to destination servers or clients
            await self.forward_message(message_dict)
        else:
            print(f"Unknown message type from server: {message_type}")

    async def forward_message(self, message_dict):
        data = message_dict.get('data', {})
        message_type = data.get('type')

        if message_type == 'chat':
            # Extract destination servers
            destination_servers = data.get('destination_servers', [])
            # If the message is intended for clients connected to this server, deliver it
            if self.address in destination_servers:
                await self.deliver_message_to_clients(message_dict)
            # Forward to other servers
            for server_address in destination_servers:
                if server_address != self.address and server_address in self.servers:
                    websocket = self.servers[server_address]
                    try:
                        await websocket.send(json.dumps(message_dict))
                    except Exception as e:
                        print(f"Error forwarding message to server {server_address}: {e}")
        elif message_type == 'public_chat':
            # Broadcast to all connected clients
            await self.deliver_message_to_clients(message_dict)
            # Forward to all other servers
            for websocket in self.servers.values():
                try:
                    await websocket.send(json.dumps(message_dict))
                except Exception as e:
                    print(f"Error forwarding public chat to server: {e}")

    async def deliver_message_to_clients(self, message_dict):
        # Deliver message to all connected clients
        for websocket in self.clients.values():
            try:
                await websocket.send(json.dumps(message_dict))
            except Exception as e:
                print(f"Error delivering message to client: {e}")

    async def send_client_list(self, websocket):
        # Prepare the client list
        servers = []
        server_entry = {
            "address": self.address,
            "clients": []
        }
        for public_key in self.client_public_keys.values():
            public_pem = export_public_key(public_key)
            public_key_b64 = base64.b64encode(public_pem).decode('utf-8')
            server_entry["clients"].append(public_key_b64)
        servers.append(server_entry)

        # Build the client list message
        client_list_message = {
            "type": "client_list",
            "servers": servers
        }

        # Send the message
        try:
            await websocket.send(json.dumps(client_list_message))
        except Exception as e:
            print(f"Error sending client list to client: {e}")

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


# Entry point
if __name__ == '__main__':
    import sys

    # Read server configuration from command line or config file
    address = SERVER_ADDRESS
    ws_port = SERVER_PORT
    http_port = HTTP_PORT
    neighbours = NEIGHBOUR_ADDRESSES

    # You can customize these values as needed
    # For example, read from a config file or command line arguments

    server = Server(address, ws_port, http_port, neighbours)
    try:
        asyncio.get_event_loop().run_until_complete(server.start())
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        print("Server shutting down")
