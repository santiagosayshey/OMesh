import pytest
import json
from app.models.message import Message
from app.utils.crypto import Crypto

def test_message_serialization():
    print("\n--- Message Serialization Test ---")
    print("Starting test...")
    message = Message(message_type="test", data={"key": "value"}, counter=1)
    print("Serializing the Message object to JSON...")
    message_json = message.to_json()
    print("Verifying the serialized JSON matches the expected structure and values...")
    assert json.loads(message_json) == {
        "type": "test",
        "data": {"key": "value"},
        "counter": 1,
        "signature": None
    }
    print("Message serialization test passed!")

def test_message_deserialization():
    print("\n--- Message Deserialization Test ---")
    print("Starting test...")
    message_json = json.dumps({
        "type": "test",
        "data": {"key": "value"},
        "counter": 1,
        "signature": None
    })
    print("Deserializing the JSON string into a Message object...")
    message = Message.from_json(message_json)
    print("Verifying the deserialized Message object has the expected attributes...")
    assert message.message_type == "test"
    assert message.data == {"key": "value"}
    assert message.counter == 1
    assert message.signature is None
    print("Message deserialization test passed!")

def test_message_signing_and_verification():
    print("\n--- Message Signing and Verification Test ---")
    print("Starting test...")
    sender_private_key, sender_public_key = Crypto.generate_rsa_key_pair()
    message = Message(message_type="test", data={"key": "value"}, counter=1)
    print("Signing the message with the sender's private key...")
    message.sign(sender_private_key)
    print("Verifying the message signature using the sender's public key...")
    assert message.verify(sender_public_key)
    print("Message signing and verification test passed!")

def test_chat_message_creation():
    print("\n--- Chat Message Creation Test ---")
    print("Starting test...")
    sender_private_key, sender_public_key = Crypto.generate_rsa_key_pair()
    recipient_public_keys = [Crypto.generate_rsa_key_pair()[1] for _ in range(3)]
    plaintext = "Hello, world!"
    counter = 1
    print("Creating a chat message with the provided data...")
    chat_message = Message.create_chat_message(sender_private_key, recipient_public_keys, plaintext, counter)
    print("Verifying the chat message has the expected attributes...")
    assert chat_message.message_type == "chat"
    assert chat_message.counter == counter
    assert len(chat_message.data["encrypted_keys"]) == len(recipient_public_keys)
    print("Verifying the chat message signature using the sender's public key...")
    assert chat_message.verify(sender_public_key)
    print("Chat message creation test passed!")

def test_public_chat_message_creation():
    print("\n--- Public Chat Message Creation Test ---")
    print("Starting test...")
    _, sender_public_key = Crypto.generate_rsa_key_pair()
    plaintext = "Hello, everyone!"
    print("Creating a public chat message with the provided data...")
    public_chat_message = Message.create_public_chat_message(sender_public_key, plaintext)
    print("Verifying the public chat message has the expected attributes...")
    assert public_chat_message.message_type == "public_chat"
    assert public_chat_message.data["sender"] == Crypto.export_public_key(sender_public_key)
    assert public_chat_message.data["message"] == plaintext
    print("Public chat message creation test passed!")