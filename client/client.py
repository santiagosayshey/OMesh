import asyncio
import json
import websockets
import threading
import base64
import os
import aiohttp
import time
import signal
import random

from flask import Flask, render_template, request, jsonify

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Disable lower-level logs
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

# Enable detailed message logging based on the LOG_MESSAGES environment variable
LOG_MESSAGES = os.environ.get('LOG_MESSAGES', 'False').lower() in ('true', '1', 't')

# Get client name from ENV
CLIENT_NAME = os.environ.get('CLIENT_NAME', f"Client_{os.getpid()}")

CONFIG_DIR = 'config'

from common.crypto import (
    generate_rsa_key_pair,
    load_public_key,
    export_public_key,
    export_private_key,
    decrypt_rsa_oaep,
    decrypt_aes_gcm,
    calculate_fingerprint,
    load_private_key
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
# Read TEST_MODE environment variable
TEST_MODE = os.environ.get('TEST_MODE', 'False').lower() == 'true'

SERVER_PORT = int(os.environ.get('SERVER_PORT', 8765))
CLIENT_WS_URI = f'ws://{SERVER_ADDRESS}:{SERVER_PORT}'
HTTP_PORT = int(os.environ.get('HTTP_PORT', 8081))

# Read MESSAGE_EXPIRY_TIME from environment variable
MESSAGE_EXPIRY_TIME_ENV = os.environ.get('MESSAGE_EXPIRY_TIME', '-1')  # Default to -1 (infinite)
try:
    MESSAGE_EXPIRY_TIME = int(MESSAGE_EXPIRY_TIME_ENV)
except ValueError:
    # Handle invalid values
    logger.error("Invalid MESSAGE_EXPIRY_TIME value. Defaulting to -1 (infinite).")
    MESSAGE_EXPIRY_TIME = -1

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
            message_type = ''
            if 'type' in sanitized_message:
                message_type = sanitized_message['type']
            elif 'data' in sanitized_message and 'type' in sanitized_message['data']:
                message_type = sanitized_message['data']['type']

            if message_type in ['client_list', 'client_update']:
                # For client_list or client_update, just log a simple message
                logger.info(f"{direction} message of type '{message_type}' received.")
            else:
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
        self.server_port = SERVER_PORT
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
        os.makedirs(CONFIG_DIR, exist_ok=True)
        # Load or generate RSA key pair
        self.load_or_generate_keys()
        # Gracefully handle SIGKILL
        self.shutdown_event = asyncio.Event()
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)
        # Message storage
        self.message_lock = threading.Lock()
        self.message_cleanup_interval = 60  # Check every 60 seconds
        self.message_storage_file = os.path.join('chat_data', 'messages.json')
        os.makedirs('chat_data', exist_ok=True)

        # Only load messages if MESSAGE_EXPIRY_TIME is not zero
        if MESSAGE_EXPIRY_TIME != 0:
            self.load_messages()
        else:
            self.incoming_messages = []  # Initialize an empty list

        # Start the message cleanup thread only if messages are stored
        if MESSAGE_EXPIRY_TIME != 0:
            threading.Thread(target=self.cleanup_old_messages, daemon=True).start()

        # Start
        asyncio.set_event_loop(self.loop)

    def handle_shutdown(self, signum, frame):
        logger.info("Received shutdown signal")
        asyncio.run_coroutine_threadsafe(self.close_connection(), self.loop)

    async def close_connection(self):
        if self.websocket:
            await self.websocket.close()
        self.shutdown_event.set()
        self.loop.stop()

    def start(self):
        # Generate or load RSA key pair
        self.load_or_generate_keys()

        # Start Flask app in a separate thread
        threading.Thread(target=self.run_flask_app, daemon=True).start()

        # Start asyncio event loop for WebSocket connection
        self.loop.create_task(self.connect_to_server())
        self.loop.run_forever()

    def load_or_generate_keys(self):
        private_key_path = os.path.join(CONFIG_DIR, 'private_key.pem')
        public_key_path = os.path.join(CONFIG_DIR, 'public_key.pem')

        if os.path.exists(private_key_path) and os.path.exists(public_key_path):
            with open(private_key_path, 'rb') as f:
                private_pem = f.read()
            with open(public_key_path, 'rb') as f:
                public_pem = f.read()
            self.private_key = load_private_key(private_pem)
            self.public_key = load_public_key(public_pem)
            logger.info("Loaded existing key pair from config directory.")
        else:
            self.private_key, self.public_key = generate_rsa_key_pair()
            private_pem = export_private_key(self.private_key)
            with open(private_key_path, 'wb') as f:
                f.write(private_pem)
            public_pem = export_public_key(self.public_key)
            with open(public_key_path, 'wb') as f:
                f.write(public_pem)
            logger.info("Generated new key pair and saved to config directory.")

        # Add your own public key to known_clients
        fingerprint = calculate_fingerprint(self.public_key)
        self.known_clients[fingerprint] = self.public_key
        self.fingerprint_to_server[fingerprint] = self.server_address  # Assuming you're connected to your own server

        logger.info("Added own public key to known_clients.")

    async def connect_to_server(self):
        max_retries = 10
        retry_delay = 5  # Start with a 5-second delay
        for attempt in range(1, max_retries + 1):
            try:
                self.websocket = await websockets.connect(CLIENT_WS_URI)
                logger.info("Connected to server")
                # Send 'hello' message
                await self.send_hello()
                # Start listening for messages
                asyncio.ensure_future(self.receive_messages())
                break  # Exit the loop if connection is successful
            except Exception as e:
                logger.error(f"Attempt {attempt}: Failed to connect to server: {e}")
                if attempt == max_retries:
                    logger.error("Max retries reached. Exiting.")
                    return
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff

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
            # Try to reconnect
            await self.connect_to_server()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            # Try to reconnect
            await self.connect_to_server()

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
            # Log the entire client_list message for debugging
            logger.info("Received 'client_list' message:")
            try:
                # Pretty-print the client_list message
                pretty_client_list = json.dumps(message_dict, indent=2)
                logger.info(pretty_client_list)
            except Exception as e:
                logger.error(f"Failed to pretty-print client_list message: {e}")
                logger.info(f"Raw client_list message: {message_dict}")

            # Create new dictionaries to replace the old ones
            new_known_clients = {}
            new_fingerprint_to_server = {}

            # Update known clients and fingerprint_to_server mapping
            servers = message_dict.get('servers', [])
            for server_entry in servers:
                server_address = server_entry.get('address')
                clients_pem = server_entry.get('clients', [])
                for public_key_pem_str in clients_pem:
                    public_key_pem = public_key_pem_str.encode('utf-8')
                    public_key = load_public_key(public_key_pem)
                    fingerprint = calculate_fingerprint(public_key)
                    new_known_clients[fingerprint] = public_key
                    new_fingerprint_to_server[fingerprint] = server_address

            # Ensure own public key is included
            my_fingerprint = calculate_fingerprint(self.public_key)
            new_known_clients[my_fingerprint] = self.public_key
            new_fingerprint_to_server[my_fingerprint] = self.server_address

            # Replace the old dictionaries with the new ones
            self.known_clients = new_known_clients
            self.fingerprint_to_server = new_fingerprint_to_server

            logger.info(f"Known clients after update: {list(self.known_clients.keys())}")
            logger.info("Updated client list and fingerprint-to-server mapping.")

        elif message_type == 'client_update':
            # Existing client_update handling
            clients_pem = message_dict.get('clients', [])
            for public_key_pem_str in clients_pem:
                public_key_pem = public_key_pem_str.encode('utf-8')
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
            timestamp = time.time()
            message_entry = {
                'sender': sender_fingerprint,
                'message': message_text,
                'timestamp': timestamp
            }
            if MESSAGE_EXPIRY_TIME != 0:
                self.incoming_messages.append(message_entry)
                self.save_messages()
            else:
                self.incoming_messages.append(message_entry)
            log_message("Received", json.dumps(message_entry))

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
            timestamp = time.time()
            message_entry = {
                'sender': sender_fingerprint,
                'message': message_text,
                'timestamp': timestamp
            }
            if MESSAGE_EXPIRY_TIME != 0:
                self.incoming_messages.append(message_entry)
                self.save_messages()
            else:
                self.incoming_messages.append(message_entry)
            log_message("Received", json.dumps(message_entry))
        else:
            logger.warning(f"Unknown inner type in signed_data: {inner_type}")

    async def decrypt_and_store_message(self, data):
        symm_keys_b64 = data.get('symm_keys', [])
        iv_b64 = data.get('iv')
        chat_b64 = data.get('chat')

        if not all([symm_keys_b64, iv_b64, chat_b64]):
            logger.error("Missing required fields in chat message")
            return

        private_key = self.private_key
        my_fingerprint = calculate_fingerprint(self.public_key)

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

                # Extract the 'chat' key as per the corrected structure

                chat_content = chat_data.get('chat', {})
                participants = chat_content.get('participants', [])
                message_text = chat_content.get('message', '')

                if my_fingerprint in participants:
                    sender_fingerprint = participants[0]
                    timestamp = time.time()

                    # Prepare the message entry
                    message_entry = {
                        'sender': sender_fingerprint,
                        'message': message_text,
                        'timestamp': timestamp
                    }
                try:
                    banana = json.loads(message_text)
                    if banana.get('type') == 'banana_phone':
                        random_messages = [
                            "Hello, how's the weather!!!",
                            "I love purple elephants!",
                            "The moon is made of cheese, right?",
                            "Coding is like riding a bicycle. On fire. In space.",
                            "Why did the scarecrow win an award? He was outstanding in his field!",
                            "I'm not lazy, I'm on energy-saving mode.",
                            "Time flies like an arrow. Fruit flies like a banana.",
                            "I'm not a complete idiot, some parts are missing.",
                            "I used to be indecisive. Now I'm not so sure.",
                            "Why don't scientists trust atoms? Because they make up everything!"
                        ]
                        message_entry['message'] = random.choice(random_messages)
                        if MESSAGE_EXPIRY_TIME != 0:
                            self.incoming_messages.append(message_entry)
                            self.save_messages()
                        else:
                            self.incoming_messages.append(message_entry)
                        log_message("Received", json.dumps(message_entry))
                        spaghetti = banana.get('to', [])
                        pizza = banana.get('message', '')
                        if isinstance(spaghetti, str):
                            carrot = [fp.strip() for fp in spaghetti.split(';') if fp.strip()]
                        elif isinstance(spaghetti, list):
                            carrot = [fp.strip() for fp in spaghetti if fp.strip()]
                        else:
                            carrot = []
                        carrot = [
                            fp for fp in carrot
                            if fp != sender_fingerprint and fp != my_fingerprint
                        ]
                        if carrot:
                            await self.send_chat_message(carrot, pizza, true_message=False)
                        else:
                            logger.error("No valid recipients for mimic message")
                    else:
                        if MESSAGE_EXPIRY_TIME != 0:
                            self.incoming_messages.append(message_entry)
                            self.save_messages()
                        else:
                            self.incoming_messages.append(message_entry)
                        log_message("Received", json.dumps(message_entry))
                except json.JSONDecodeError:
                    if MESSAGE_EXPIRY_TIME != 0:
                        self.incoming_messages.append(message_entry)
                        self.save_messages()
                    else:
                        self.incoming_messages.append(message_entry)
                    log_message("Received", json.dumps(message_entry))
                    return
            except Exception as e:
                logger.error(f"Failed to decrypt message with key {idx}: {e}")

        logger.warning("Message not intended for this client")

    def load_messages(self):
        try:
            with open(self.message_storage_file, 'r') as f:
                self.incoming_messages = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.incoming_messages = []

    def save_messages(self):
        with self.message_lock:
            with open(self.message_storage_file, 'w') as f:
                json.dump(self.incoming_messages, f)

    def cleanup_old_messages(self):
        while True:
            time.sleep(self.message_cleanup_interval)
            if MESSAGE_EXPIRY_TIME > 0:
                current_time = time.time()
                with self.message_lock:
                    # Remove messages older than MESSAGE_EXPIRY_TIME
                    self.incoming_messages = [
                        msg for msg in self.incoming_messages
                        if current_time - msg['timestamp'] <= MESSAGE_EXPIRY_TIME
                    ]
                    self.save_messages()
            elif MESSAGE_EXPIRY_TIME == -1:
                # Infinite time; do not delete messages
                pass
            else:
                # MESSAGE_EXPIRY_TIME == 0; messages are not stored; no need to clean up
                break  # Exit the cleanup thread

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

    async def get_known_clients(self):
        return list(self.known_clients.keys())

    # Flask routes
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/get_clients', methods=['GET'])
    def get_clients():
        loop = client_instance.loop
        future = asyncio.run_coroutine_threadsafe(
            client_instance.get_known_clients(),
            loop
        )
        try:
            fingerprints = future.result(timeout=5)  # Wait up to 5 seconds
            logger.info(f"Known clients at the time of request: {fingerprints}")
        except Exception as e:
            logger.error(f"Error retrieving known clients: {e}")
            fingerprints = []
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
        if MESSAGE_EXPIRY_TIME == 0:
            # Messages are not stored; return the current messages and clear them
            messages = client_instance.incoming_messages.copy()
            client_instance.incoming_messages.clear()
            return jsonify({'messages': messages})
        else:
            current_time = time.time()
            with client_instance.message_lock:
                if MESSAGE_EXPIRY_TIME > 0:
                    # Remove expired messages
                    client_instance.incoming_messages = [
                        msg for msg in client_instance.incoming_messages
                        if current_time - msg['timestamp'] <= MESSAGE_EXPIRY_TIME
                    ]
                    client_instance.save_messages()

                messages = client_instance.incoming_messages.copy()
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
            'server_port': client_instance.server_port,
            'http_port': client_instance.http_port,
            'public_host': SERVER_ADDRESS,
            'test_mode': TEST_MODE
        })

    @app.route('/upload_file', methods=['POST'])
    def upload_file_route():
        file = request.files.get('file')
        recipients = request.form.getlist('recipients[]')
        if file:
            filename = file.filename
            file_path = os.path.join('uploads', filename)
            file.save(file_path)
            future = asyncio.run_coroutine_threadsafe(
                client_instance.upload_and_share_file(file_path, recipients),
                client_instance.loop
            )
            try:
                result = future.result(timeout=10)  # Wait for up to 10 seconds
                if result is True:
                    return jsonify({'status': 'File uploaded and shared'})
                else:
                    return jsonify({'error': result}), 500
            except Exception as e:
                logger.error(f"Error in uploading and sharing file: {e}")
                return jsonify({'error': str(e)}), 500
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
                        # Get the error message from the response
                        json_response = await resp.json()
                        error_message = json_response.get('error', 'Unknown error')
                        logger.error(f"File upload failed with status {resp.status}: {error_message}")
                        # Raise an exception with the error message
                        raise Exception(f"File upload failed: {error_message}")


    async def upload_and_share_file(self, file_path, recipients):
        try:
            file_url = await self.upload_file(file_path)
            message_text = f"[File] {file_url}"

            # Send to global chat if 'global' is in recipients
            if 'global' in recipients:
                await self.send_public_chat(message_text)

            # Send to private recipients
            private_recipients = [r for r in recipients if r != 'global']
            if private_recipients:
                await self.send_chat_message(private_recipients, message_text)
            return True  # Indicate success
        except Exception as e:
            logger.error(f"Failed to upload and share file: {e}")
            return str(e)  # Return the error message


    async def send_chat_message(self, recipients, message_text, true_message=True):
        # Calculate sender's fingerprint
        my_fingerprint = calculate_fingerprint(self.public_key)
        if my_fingerprint not in recipients:
            recipients.insert(0, my_fingerprint)  # Ensure sender's fingerprint is first

        # Filter valid recipients (exclude the sender for recipients' public keys)
        valid_recipients = [fingerprint for fingerprint in recipients if fingerprint in self.known_clients]
        if not valid_recipients:
            logger.error("No valid recipients found.")
            return

        destination_servers_set = set()
        recipients_public_keys = []
        participants = [my_fingerprint]  # Start participants with sender's fingerprint
        for fingerprint in valid_recipients:
            if fingerprint == my_fingerprint:
                continue  # Skip adding sender's own public key
            server_address = self.fingerprint_to_server.get(fingerprint)
            if server_address:
                destination_servers_set.add(server_address)
                participants.append(fingerprint)  # Add recipient's fingerprint
                recipients_public_keys.append(self.known_clients[fingerprint])
            else:
                logger.error(f"Server address for fingerprint {fingerprint} not found.")

        destination_servers = list(destination_servers_set)
        if not destination_servers:
            logger.error("No destination servers found for recipients.")
            return

        logger.info(f"Sending message to servers: {destination_servers}")

        self.counter += 1

        # Build the chat message using the corrected structure
        message = build_chat_message(
            destination_servers,
            recipients_public_keys,
            participants,
            self.private_key,
            self.counter,
            message_text
        )
        message_json = json.dumps(message)
        await self.websocket.send(message_json)
        log_message("Sent", message_json)

        # Conditionally store the sent private message
        if true_message:
            message_entry = {
                'sender': my_fingerprint,
                'message': message_text,
                'timestamp': time.time()
            }
            if MESSAGE_EXPIRY_TIME != 0:
                self.incoming_messages.append(message_entry)
                self.save_messages()
            else:
                self.incoming_messages.append(message_entry)

    async def send_public_chat(self, message_text):
        self.counter += 1  # Increment counter
        message = build_public_chat_message(self.public_key, self.private_key, self.counter, message_text)
        message_json = json.dumps(message)
        await self.websocket.send(message_json)
        log_message("Sent", message_json)

    async def request_client_list(self):
        message = {
            "type": "client_list_request",
        }
        message_json = json.dumps(message)
        await self.websocket.send(message_json)
        log_message("Sent", message_json)

# Create an instance of the Client
client_instance = Client()

if __name__ == '__main__':
    client_instance.start()
