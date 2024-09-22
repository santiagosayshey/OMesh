from app.utils.crypto import Crypto
from app.models.message import Message
import json
import base64

class User:
    def __init__(self):
        self.private_key, self.public_key = Crypto.generate_rsa_key_pair()
        self.fingerprint = Crypto.generate_fingerprint(self.public_key)
        self.counter = 0
        self.home_server = None

    def set_home_server(self, server_address):
        self.home_server = server_address

    def create_hello_message(self):
        self.counter += 1
        data = {
            "type": "hello",
            "public_key": Crypto.export_public_key(self.public_key)
        }
        return Message.create_message("hello", data, self.counter, self.private_key)

    def create_chat_message(self, recipients, destination_servers, plaintext):
        self.counter += 1
        aes_key = Crypto.AES_KEY_LENGTH * b"x"  # Replace with secure random key generation
        iv, ciphertext, tag = Crypto.aes_encrypt(plaintext.encode("utf-8"), aes_key)

        encrypted_keys = [Crypto.rsa_encrypt(aes_key, recipient.public_key) for recipient in recipients]

        chat_content = {
            "participants": [self.fingerprint] + [recipient.fingerprint for recipient in recipients],
            "message": plaintext
        }
        encrypted_chat = Crypto.aes_encrypt(json.dumps(chat_content).encode("utf-8"), aes_key)

        data = {
            "type": "chat",
            "destination_servers": destination_servers,
            "iv": base64.b64encode(iv).decode("utf-8"),
            "symm_keys": encrypted_keys,
            "chat": base64.b64encode(encrypted_chat[1]).decode("utf-8")
        }

        return Message.create_message("chat", data, self.counter, self.private_key)

    def create_public_chat_message(self, plaintext):
        self.counter += 1
        data = {
            "type": "public_chat",
            "sender": self.fingerprint,
            "message": plaintext
        }
        return Message.create_message("public_chat", data, self.counter, self.private_key)

    def create_client_list_request(self):
        self.counter += 1
        return Message.create_message("client_list_request", {}, self.counter, self.private_key)

    def receive_message(self, message):
        if not message.verify(self.public_key):
            raise ValueError("Message signature verification failed")
        
        if not message.verify_counter(self.counter):
            raise ValueError("Message counter verification failed")

        if message.message_type == "chat":
            return self.handle_chat_message(message)
        elif message.message_type == "public_chat":
            return self.handle_public_chat_message(message)
        elif message.message_type == "client_list":
            return self.handle_client_list_message(message)
        else:
            raise ValueError(f"Unknown message type: {message.message_type}")

    def handle_chat_message(self, message):
        encrypted_key = message.data["symm_keys"][0]  # Assume we're the first recipient for simplicity
        aes_key = Crypto.rsa_decrypt(encrypted_key, self.private_key)
        iv = base64.b64decode(message.data["iv"])
        encrypted_chat = base64.b64decode(message.data["chat"])
        decrypted_chat = Crypto.aes_decrypt(iv, encrypted_chat, None, aes_key)  # Note: tag is missing in the protocol
        chat_content = json.loads(decrypted_chat.decode("utf-8"))
        return chat_content

    def handle_public_chat_message(self, message):
        return message.data

    def handle_client_list_message(self, message):
        return message.data

    def upload_file(self, file_path):
        # Implement file upload logic here
        pass

    def download_file(self, file_url):
        # Implement file download logic here
        pass