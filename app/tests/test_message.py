import pytest
import json

from app.models.message import Message
from app.utils.crypto import Crypto

def test_message_serialization():
    message = Message(message_type="test", data={"key": "value"}, counter=1)
    message_json = message.to_json()
    assert json.loads(message_json) == {
        "type": "test",
        "data": {"key": "value"},
        "counter": 1,
        "signature": None
    }

def test_message_deserialization():
    message_json = json.dumps({
        "type": "test",
        "data": {"key": "value"},
        "counter": 1,
        "signature": None
    })
    message = Message.from_json(message_json)
    assert message.message_type == "test"
    assert message.data == {"key": "value"}
    assert message.counter == 1
    assert message.signature is None

def test_message_signing_and_verification():
    sender_private_key, sender_public_key = Crypto.generate_rsa_key_pair()
    message = Message(message_type="test", data={"key": "value"}, counter=1)
    message.sign(sender_private_key)
    assert message.verify(sender_public_key)

def test_chat_message_creation():
    sender_private_key, sender_public_key = Crypto.generate_rsa_key_pair()
    recipient_public_keys = [Crypto.generate_rsa_key_pair()[1] for _ in range(3)]
    plaintext = "Hello, world!"
    counter = 1
    chat_message = Message.create_chat_message(sender_private_key, recipient_public_keys, plaintext, counter)
    assert chat_message.message_type == "chat"
    assert chat_message.counter == counter
    assert len(chat_message.data["encrypted_keys"]) == len(recipient_public_keys)
    assert chat_message.verify(sender_public_key)

def test_public_chat_message_creation():
    _, sender_public_key = Crypto.generate_rsa_key_pair()
    plaintext = "Hello, everyone!"
    public_chat_message = Message.create_public_chat_message(sender_public_key, plaintext)
    assert public_chat_message.message_type == "public_chat"
    assert public_chat_message.data["sender"] == Crypto.export_public_key(sender_public_key)
    assert public_chat_message.data["message"] == plaintext