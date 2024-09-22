import pytest
import json
from ..utils.crypto import Crypto
from ..models.message import Message

@pytest.fixture
def key_pair():
    return Crypto.generate_rsa_key_pair()

@pytest.fixture
def sample_message():
    return Message(
        message_type="test",
        data={"key": "value"},
        counter=1
    )

def test_message_creation():
    message = Message("test", {"key": "value"}, 1)
    assert message.message_type == "test"
    assert message.data == {"key": "value"}
    assert message.counter == 1
    assert message.signature is None

def test_message_to_json(sample_message):
    json_str = sample_message.to_json()
    data = json.loads(json_str)
    assert data["type"] == "signed_data"
    assert data["data"] == {"key": "value"}
    assert data["counter"] == 1
    assert data["signature"] is None

def test_message_from_json():
    json_str = json.dumps({
        "type": "signed_data",
        "data": {"key": "value"},
        "counter": 1,
        "signature": None
    })
    message = Message.from_json(json_str)
    assert message.message_type == "signed_data"
    assert message.data == {"key": "value"}
    assert message.counter == 1
    assert message.signature is None

def test_message_sign_and_verify(key_pair, sample_message):
    private_key, public_key = key_pair
    sample_message.sign(private_key)
    assert sample_message.signature is not None
    assert sample_message.verify(public_key)

def test_message_verify_with_wrong_key(key_pair, sample_message):
    private_key, _ = key_pair
    _, wrong_public_key = Crypto.generate_rsa_key_pair()
    sample_message.sign(private_key)
    assert not sample_message.verify(wrong_public_key)

def test_verify_counter():
    message = Message("test", counter=5)
    assert message.verify_counter(4)
    assert not message.verify_counter(5)
    assert not message.verify_counter(6)

def test_create_message():
    message = Message.create_message("test", {"key": "value"}, 1)
    assert message.message_type == "test"
    assert message.data == {"key": "value"}
    assert message.counter == 1
    assert message.signature is None

def test_create_signed_message(key_pair):
    private_key, public_key = key_pair
    message = Message.create_message("test", {"key": "value"}, 1, private_key)
    assert message.message_type == "test"
    assert message.data == {"key": "value"}
    assert message.counter == 1
    assert message.signature is not None
    assert message.verify(public_key)