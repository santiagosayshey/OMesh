# client/client.py

import asyncio
import json
import websockets
import json
import threading
import base64
import os

from flask import Flask, render_template, request, jsonify
from flask_sock import Sock

import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from common.crypto import (
    generate_rsa_key_pair,
    load_public_key,
    load_private_key,
    export_public_key,
    export_private_key,
    sign_data,
    verify_signature,
    encrypt_rsa_oaep,
    decrypt_rsa_oaep,
    encrypt_aes_gcm,
    decrypt_aes_gcm,
    calculate_fingerprint,
    generate_aes_key,
    generate_iv,
)
from common.protocol import (
    build_hello_message,
    build_chat_message,
    build_public_chat_message,
    build_client_list_request,
    parse_message,
    verify_signed_message,
    validate_message_format,
)

# Configuration
SERVER_ADDRESS = os.environ.get('SERVER_ADDRESS', 'server1')
SERVER_PORT = int(os.environ.get('SERVER_PORT', 8765))
CLIENT_WS_URI = f'ws://{SERVER_ADDRESS}:{SERVER_PORT}'

# Flask app
app = Flask(__name__)
sock = Sock(app)

class Client:
    def __init__(self):
        self.server_address = SERVER_ADDRESS
        self.websocket = None
        self.private_key = None
        self.public_key = None
        self.counter = 0
        self.known_clients = {}  # {fingerprint: public_key}
        self.last_counters = {}  # {fingerprint: last_counter}
        self.incoming_messages = []
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def start(self):
        # Generate or load RSA key pair
        self.load_or_generate_keys()

        # Start Flask app in a separate thread
        threading.Thread(target=self.run_flask_app).start()

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
            print("Connected to server")

            # Send 'hello' message
            await self.send_hello()

            # Start listening for messages
            asyncio.ensure_future(self.receive_messages())
        except Exception as e:
            print(f"Failed to connect to server: {e}")

    async def send_hello(self):
        public_pem = export_public_key(self.public_key)
        public_key_b64 = base64.b64encode(public_pem).decode('utf-8')
        data_dict = {
            "type": "hello",
            "public_key": public_key_b64
        }
        message = {
            "type": "hello",  # Add this line
            "data": data_dict
        }
        message_json = json.dumps(message)
        await self.websocket.send(message_json)
        print("Sent 'hello' message to server")


    async def receive_messages(self):
        try:
            async for message in self.websocket:
                message_dict, error = parse_message(message)
                if error:
                    print(f"Error parsing message from server: {error}")
                    continue

                # Handle incoming message
                await self.handle_incoming_message(message_dict)
        except websockets.ConnectionClosed:
            print("Connection to server closed")

    async def handle_incoming_message(self, message_dict):
        # Extract message_type
        if "type" in message_dict:
            message_type = message_dict["type"]
        elif "data" in message_dict and "type" in message_dict["data"]:
            message_type = message_dict["data"]["type"]
        else:
            print("Received message without 'type'")
            return
        data = message_dict.get('data', {})

        if message_type == 'client_list':
            # Update known clients
            servers = message_dict.get('servers', [])
            for server_entry in servers:
                clients_b64 = server_entry.get('clients', [])
                for public_key_b64 in clients_b64:
                    public_key_pem = base64.b64decode(public_key_b64.encode('utf-8'))
                    public_key = load_public_key(public_key_pem)
                    fingerprint = calculate_fingerprint(public_key)
                    self.known_clients[fingerprint] = public_key
            print("Updated client list")
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
        else:
            print(f"Unknown message type: {message_type}")

    async def decrypt_and_store_message(self, data):
        symm_keys_b64 = data.get('symm_keys', [])
        iv_b64 = data.get('iv')
        chat_b64 = data.get('chat')

        if not all([symm_keys_b64, iv_b64, chat_b64]):
            print("Missing required fields in chat message")
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
                    print(f"Received message from {sender_fingerprint}: {message_text}")
                    return
            except Exception as e:
                print(f"Failed to decrypt message with key {idx}: {e}")

        print("Message not intended for this client")

    def run_flask_app(self):
        # Start Flask app
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

    # Flask routes
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/get_clients', methods=['GET'])
    def get_clients():
        fingerprints = list(client_instance.known_clients.keys())
        logger.debug(f"Sending client list: {fingerprints}")
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
        return jsonify({'fingerprint': fingerprint})

    async def send_chat_message(self, recipients, message_text):
        recipients_public_keys = [self.known_clients[fingerprint] for fingerprint in recipients if fingerprint in self.known_clients]
        destination_servers = [self.server_address]  # Assuming all recipients are on the same server

        message = build_chat_message(
            destination_servers,
            recipients_public_keys,
            self.private_key,
            message_text
        )
        message_json = json.dumps(message)
        await self.websocket.send(message_json)
        print(f"Sent message to {recipients}")

    async def send_public_chat(self, message_text):
        message = build_public_chat_message(self.public_key, message_text)
        message_json = json.dumps(message)
        await self.websocket.send(message_json)
        print("Sent public message")
    
    async def request_client_list(self):
        message = {
            "type": "client_list_request"
        }
        message_json = json.dumps(message)
        await self.websocket.send(message_json)
        logger.info("Requested client list")

# Create an instance of the Client
client_instance = Client()

if __name__ == '__main__':
    client_instance.start()
