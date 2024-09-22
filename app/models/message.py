import json
import base64
import os
from ..utils.crypto import Crypto

class Message:
    def __init__(self, message_type, data=None, counter=None, signature=None):
        self.message_type = message_type
        self.data = data
        self.counter = counter
        self.signature = signature

    def to_json(self):
        return json.dumps({
            "type": self.message_type,
            "data": self.data,
            "counter": self.counter,
            "signature": self.signature
        })

    @staticmethod
    def from_json(json_string):
        data = json.loads(json_string)
        return Message(
            message_type=data["type"],
            data=data["data"],
            counter=data["counter"],
            signature=data["signature"]
        )

    def sign(self, private_key):
        message_data = {
            "type": self.message_type,
            "data": self.data,
            "counter": self.counter
        }
        message_bytes = json.dumps(message_data).encode("utf-8")
        self.signature = Crypto.rsa_sign(message_bytes, private_key)

    def verify(self, public_key):
        message_data = {
            "type": self.message_type,
            "data": self.data,
            "counter": self.counter
        }
        message_bytes = json.dumps(message_data).encode("utf-8")
        return Crypto.rsa_verify(message_bytes, self.signature, public_key)

    @staticmethod
    def create_chat_message(sender_private_key, recipient_public_keys, plaintext, counter):
        # Generate a random AES key
        aes_key = os.urandom(32)

        # Encrypt the plaintext using AES
        iv, ciphertext, tag = Crypto.aes_encrypt(plaintext.encode("utf-8"), aes_key)

        # Encrypt the AES key with each recipient's public key
        encrypted_keys = [Crypto.rsa_encrypt(aes_key, public_key) for public_key in recipient_public_keys]

        data = {
            "iv": base64.b64encode(iv).decode("utf-8"),
            "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
            "tag": base64.b64encode(tag).decode("utf-8"),
            "encrypted_keys": encrypted_keys
        }

        message = Message(message_type="chat", data=data, counter=counter)
        message.sign(sender_private_key)
        return message

    @staticmethod
    def create_public_chat_message(sender_public_key, plaintext):
        data = {
            "sender": Crypto.export_public_key(sender_public_key),
            "message": plaintext
        }
        return Message(message_type="public_chat", data=data)