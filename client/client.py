import asyncio
import json
import websockets
import threading
import base64
import os
import aiohttp

from flask import Flask, render_template, request, jsonify

import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Disable lower-level logs
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

# Enable detailed message logging based on the LOG_MESSAGES environment variable
LOG_MESSAGES = os.environ.get('LOG_MESSAGES', 'False').lower() in ('true','1', 't')
# Get client name from ENV
CLIENT_NAME = os.environ.get('CLIENT_NAME', f"Client_{os.getpid()}")

from common.crypto import (
    generate_rsa_key_pair,
    load_public_key,
    export_public_key,
    export_private_key,
    decrypt_rsa_oaep,
    decrypt_aes_gcm,
    calculate_fingerprint,
)
from common.protocol import (
    build_hello_message,
    build_chat_message,
    build_public_chat_message,
    parse_message,
    verify_signed_message,
    validate_message_format,
)

# Configuration
SERVER_ADDRESS = os.environ.get('SERVER_ADDRESS', 'server1')
SERVER_PORT = int(os.environ.get('SERVER_PORT', 8765))
CLIENT_WS_URI = f'ws://{SERVER_ADDRESS}:{SERVER_PORT}'
PUBLIC_HOST = os.environ.get('PUBLIC_HOST', 'localhost')
HTTP_PORT = int(os.environ.get('HTTP_PORT', 8081))

# Flask app
app = Flask(__name__)

os.makedirs('uploads', exist_ok=True)

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

class Client:
    def __init__(self):
        self.server_address = SERVER_ADDRESS
        self.server_port = SERVER_PORT  # Added server_port
        self.websocket = None
        self.private_key = None
        self.public_key = None
        self.counter = 0  # Initialize counter to 0
        self.known_clients = {}  # {fingerprint: public_key}
        self.fingerprint_to_server = {}  # {fingerprint: server_address}
        self.last_counters = {}  # {fingerprint: last_counter}
        self.incoming_messages = []
        self.name = CLIENT_NAME
        self.http_port = HTTP_PORT
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def start(self):
        # Generate or load RSA key pair
        self.load_or_generate_keys()

        # Start Flask app in a separate thread
        threading.Thread(target=self.run_flask_app, daemon=True).start()

        # Start asyncio event loop for WebSocket connection
        self.loop.create_task(self.connect_to_server())
        self.loop.run_forever()

    def load_or_generate_keys(self):
        # Always generate new key pair
        self.private_key, self.public_key = generate_rsa_key_pair()
        # Save keys to files
        private_pem = export_private_key(self.private_key)
        with open('private_key.pem', 'wb') as f:
            f.write(private_pem)
        public_pem = export_public_key(self.public_key)
        with open('public_key.pem', 'wb') as f:
            f.write(public_pem)

    async def connect_to_server(self):
        try:
            self.websocket = await websockets.connect(CLIENT_WS_URI)
            logger.info("Connected to server")

            # Send 'hello' message
            await self.send_hello()

            # Start listening for messages
            asyncio.ensure_future(self.receive_messages())
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")

    async def send_hello(self):
        self.counter += 1  # Increment counter
        message = build_hello_message(self.public_key, self.private_key, self.counter)
        message_json = json.dumps(message)
        await self.websocket.send(message_json)
        log_message("Sent", message_json)

    async def receive_messages(self):
        try:
            async for message in self.websocket:
                message_dict, error = parse_message(message)
                if error:
                    logger.error(f"Error parsing message from server: {error}")
                    continue

                # Log the received message without sensitive fields
                log_message("Received", message)

                # Handle incoming message
                await self.handle_incoming_message(message_dict)
        except websockets.ConnectionClosed:
            logger.info("Connection to server closed")

    async def handle_incoming_message(self, message_dict):
        # Extract message_type
        if "type" in message_dict:
            message_type = message_dict["type"]
        elif "data" in message_dict and "type" in message_dict["data"]:
            message_type = message_dict["data"]["type"]
        else:
            logger.warning("Unknown message type received.")
            return
        data = message_dict.get('data', {})
        if message_type == 'signed_data':
            # Handle signed_data message
            await self.handle_signed_data_message(message_dict)
        elif message_type == 'client_list':
            # Update known clients and fingerprint_to_server mapping
            servers = message_dict.get('servers', [])
            for server_entry in servers:
                server_address = server_entry.get('address')
                clients_b64 = server_entry.get('clients', [])
                for public_key_b64 in clients_b64:
                    public_key_pem = base64.b64decode(public_key_b64.encode('utf-8'))
                    public_key = load_public_key(public_key_pem)
                    fingerprint = calculate_fingerprint(public_key)
                    self.known_clients[fingerprint] = public_key
                    self.fingerprint_to_server[fingerprint] = server_address
            logger.info("Updated client list and fingerprint-to-server mapping.")

        elif message_type == 'client_update':
            # Update known clients and fingerprint_to_server mapping
            clients_b64 = message_dict.get('clients', [])
            for public_key_b64 in clients_b64:
                public_key_pem = base64.b64decode(public_key_b64.encode('utf-8'))
                public_key = load_public_key(public_key_pem)
                fingerprint = calculate_fingerprint(public_key)
                self.known_clients[fingerprint] = public_key
                self.fingerprint_to_server[fingerprint] = self.server_address  # Assuming updates are from home server
            logger.info("Updated client list from client_update.")

        elif message_type == 'chat':
            # Handle chat message
            await self.decrypt_and_store_message(data)
        elif message_type == 'public_chat':
            # Handle public chat message
            sender_fingerprint = data.get('sender')
            message_text = data.get('message')
            self.incoming_messages.append({
                'sender': sender_fingerprint,
                'message': message_text
            })
            log_message("Received", json.dumps({
                'sender': sender_fingerprint,
                'message': message_text
            }))
        else:
            logger.warning(f"Unknown message type: {message_type}")

    async def handle_signed_data_message(self, message_dict):
        data = message_dict.get('data', {})
        inner_type = data.get('type')

        if inner_type == 'chat':
            # Handle chat message
            await self.decrypt_and_store_message(data)
        elif inner_type == 'public_chat':
            # Handle public chat message
            sender_fingerprint = data.get('sender')
            message_text = data.get('message')
            self.incoming_messages.append({
                'sender': sender_fingerprint,
                'message': message_text
            })
            log_message("Received", json.dumps({
                'sender': sender_fingerprint,
                'message': message_text
            }))
        else:
            logger.warning(f"Unknown inner type in signed_data: {inner_type}")

    async def decrypt_and_store_message(self, data):
        symm_keys_b64 = data.get('symm_keys', [])
        iv_b64 = data.get('iv')
        chat_b64 = data.get('chat')

        if not all([symm_keys_b64, iv_b64, chat_b64]):
            logger.error("Missing required fields in chat message")
            return

        # Try to decrypt the symmetric key
        private_key = self.private_key
        my_fingerprint = calculate_fingerprint(self.public_key)

        # Decrypt the chat data first
        iv = base64.b64decode(iv_b64.encode('utf-8'))
        cipher_and_tag = base64.b64decode(chat_b64.encode('utf-8'))
        ciphertext = cipher_and_tag[:-16]
        tag = cipher_and_tag[-16:]

        for idx, symm_key_b64 in enumerate(symm_keys_b64):
            symm_key_encrypted = base64.b64decode(symm_key_b64.encode('utf-8'))
            try:
                symm_key = decrypt_rsa_oaep(symm_key_encrypted, private_key)
                plaintext_bytes = decrypt_aes_gcm(ciphertext, symm_key, iv, tag)
                chat_data = json.loads(plaintext_bytes.decode('utf-8'))

                participants = chat_data.get('participants', [])
                if my_fingerprint in participants:
                    sender_fingerprint = participants[0]
                    message_text = chat_data['message']
                    self.incoming_messages.append({
                        'sender': sender_fingerprint,
                        'message': message_text
                    })
                    log_message("Received", json.dumps({
                        'sender': sender_fingerprint,
                        'message': message_text
                    }))
                    return
            except Exception as e:
                logger.error(f"Failed to decrypt message with key {idx}: {e}")

        logger.warning("Message not intended for this client")

    def run_flask_app(self):
        # Suppress Flask's werkzeug logs by setting the logger level to ERROR
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(logging.ERROR)
        werkzeug_logger.propagate = False

        # Disable Flask's default logger
        app.logger.disabled = True
        flask_logger = logging.getLogger('flask')
        flask_logger.setLevel(logging.ERROR)
        flask_logger.propagate = False

        # Start Flask app
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

    # Flask routes
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/get_clients', methods=['GET'])
    def get_clients():
        fingerprints = list(client_instance.known_clients.keys())
        return jsonify({'clients': fingerprints})

    @app.route('/send_message', methods=['POST'])
    def send_message():
        data = request.json
        message_text = data.get('message')
        recipients = data.get('recipients', [])
        asyncio.run_coroutine_threadsafe(
            client_instance.send_chat_message(recipients, message_text),
            client_instance.loop
        )
        return jsonify({'status': 'Message sent'})

    @app.route('/send_public_message', methods=['POST'])
    def send_public_message():
        data = request.json
        message_text = data.get('message')
        asyncio.run_coroutine_threadsafe(
            client_instance.send_public_chat(message_text),
            client_instance.loop
        )
        return jsonify({'status': 'Public message sent'})

    @app.route('/get_messages', methods=['GET'])
    def get_messages():
        messages = client_instance.incoming_messages.copy()
        client_instance.incoming_messages.clear()
        return jsonify({'messages': messages})

    @app.route('/request_client_list', methods=['GET'])
    def request_client_list():
        asyncio.run_coroutine_threadsafe(
            client_instance.request_client_list(),
            client_instance.loop
        )
        return jsonify({'status': 'Client list requested'})

    @app.route('/get_fingerprint', methods=['GET'])
    def get_fingerprint():
        fingerprint = calculate_fingerprint(client_instance.public_key)
        return jsonify({
            'fingerprint': fingerprint,
            'name': client_instance.name,
            'server_address': client_instance.server_address,
            'server_port': client_instance.server_port
        })

    @app.route('/upload_file', methods=['POST'])
    def upload_file_route():
        file = request.files.get('file')
        recipients = request.form.getlist('recipients[]')
        if file:
            filename = file.filename
            file_path = os.path.join('uploads', filename)
            file.save(file_path)
            asyncio.run_coroutine_threadsafe(
                client_instance.upload_and_share_file(file_path, recipients),
                client_instance.loop
            )
            return jsonify({'status': 'File uploaded and shared'})
        else:
            return jsonify({'error': 'No file provided'}), 400

    async def upload_file(self, file_path):
        url = f'http://{self.server_address}:{self.http_port}/api/upload'
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(url, data=form) as resp:
                    if resp.status == 200:
                        json_response = await resp.json()
                        file_url = json_response.get('file_url')
                        return file_url
                    else:
                        error_message = await resp.text()
                        logger.error(f"File upload failed with status {resp.status}: {error_message}")
                        return None

    async def upload_and_share_file(self, file_path, recipients):
        file_url = await self.upload_file(file_path)
        if file_url:
            message_text = f"[File] {file_url}"

            # Send to global chat if 'global' is in recipients
            if 'global' in recipients:
                await self.send_public_chat(message_text)

            # Send to private recipients
            private_recipients = [r for r in recipients if r != 'global']
            if private_recipients:
                await self.send_chat_message(private_recipients, message_text)
        else:
            logger.error("Failed to upload and share file.")

    async def send_chat_message(self, recipients, message_text):
        valid_recipients = [fingerprint for fingerprint in recipients if fingerprint in self.known_clients]
        if not valid_recipients:
            logger.error("No valid recipients found.")
            return

        destination_servers_set = set()
        recipients_public_keys = []
        for fingerprint in valid_recipients:
            server_address = self.fingerprint_to_server.get(fingerprint)
            if server_address:
                destination_servers_set.add(server_address)
                recipients_public_keys.append(self.known_clients[fingerprint])
            else:
                logger.error(f"Server address for fingerprint {fingerprint} not found.")

        destination_servers = list(destination_servers_set)
        if not destination_servers:
            logger.error("No destination servers found for recipients.")
            return

        logger.info(f"Sending message to servers: {destination_servers}")

        self.counter += 1

        message = build_chat_message(
            destination_servers,
            recipients_public_keys,
            self.private_key,
            self.counter,
            message_text
        )
        message_json = json.dumps(message)
        await self.websocket.send(message_json)
        log_message("Sent", message_json)

    async def send_public_chat(self, message_text):
        self.counter += 1  # Increment counter
        message = build_public_chat_message(self.public_key, self.private_key, self.counter, message_text)
        message_json = json.dumps(message)
        await self.websocket.send(message_json)
        log_message("Sent", message_json)

    async def request_client_list(self):
        message = {
            "type": "client_list_request"
        }
        message_json = json.dumps(message)
        await self.websocket.send(message_json)
        log_message("Sent", message_json)

# Create an instance of the Client
client_instance = Client()

if __name__ == '__main__':
    client_instance.start()
