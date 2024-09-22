import json
from ..utils.crypto import Crypto

class Message:
    def __init__(self, message_type, data=None, counter=None, signature=None):
        self.message_type = message_type
        self.data = data
        self.counter = counter
        self.signature = signature

    def to_json(self):
        return json.dumps({
            "type": "signed_data",
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

    def verify_counter(self, last_counter):
        if self.counter is None or last_counter is None:
            return False
        return self.counter > last_counter

    @staticmethod
    def create_message(message_type, data, counter=None, private_key=None):
        message = Message(message_type=message_type, data=data, counter=counter)
        if private_key:
            message.sign(private_key)
        return message