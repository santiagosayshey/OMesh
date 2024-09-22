import pytest
from unittest.mock import patch, MagicMock
from app.models.user import User
from app.models.message import Message
from app.utils.crypto import Crypto
import json
import base64

class MockPrivateKey:
    def __init__(self):
        pass

    def sign(self, message, padding, algorithm):
        return b'mock_signature'

class MockPublicKey:
    def __init__(self):
        pass

    def verify(self, signature, message, padding, algorithm):
        return True

@pytest.fixture
def mock_crypto():
    with patch('app.models.user.Crypto') as mock:
        mock.generate_rsa_key_pair.return_value = (MockPrivateKey(), MockPublicKey())
        mock.generate_fingerprint.return_value = 'mock_fingerprint'
        mock.export_public_key.return_value = 'mock_exported_public_key'
        mock.rsa_encrypt.return_value = 'mock_encrypted_data'
        mock.rsa_decrypt.return_value = b'mock_decrypted_data'
        mock.aes_encrypt.return_value = (b'mock_iv', b'mock_ciphertext', b'mock_tag')
        mock.aes_decrypt.return_value = json.dumps({"mock": "decrypted_data"}).encode()
        mock.AES_KEY_LENGTH = 32
        yield mock

@pytest.fixture
def user(mock_crypto):
    return User()

@pytest.fixture
def mock_message():
    message = MagicMock(spec=Message)
    message.verify.return_value = True
    message.verify_counter.return_value = True
    return message

@pytest.fixture
def mock_recipient(mock_crypto):
    recipient = MagicMock()
    recipient.public_key = MockPublicKey()
    recipient.fingerprint = 'mock_recipient_fingerprint'
    return recipient

def test_user_initialization(user):
    assert isinstance(user.private_key, MockPrivateKey)
    assert isinstance(user.public_key, MockPublicKey)
    assert user.fingerprint == 'mock_fingerprint'
    assert user.counter == 0
    assert user.home_server is None

def test_set_home_server(user):
    user.set_home_server('test_server.com')
    assert user.home_server == 'test_server.com'

def test_create_hello_message(user, mock_crypto):
    hello_message = user.create_hello_message()
    assert hello_message.message_type == 'hello'
    assert hello_message.data == {
        'type': 'hello',
        'public_key': 'mock_exported_public_key'
    }
    assert hello_message.counter == 1

def test_create_chat_message(user, mock_crypto, mock_recipient):
    chat_message = user.create_chat_message([mock_recipient], ['test_server.com'], 'Test message')
    assert chat_message.message_type == 'chat'
    assert chat_message.data['type'] == 'chat'
    assert chat_message.data['destination_servers'] == ['test_server.com']
    assert 'iv' in chat_message.data
    assert 'symm_keys' in chat_message.data
    assert 'chat' in chat_message.data
    assert chat_message.counter == 1

def test_create_public_chat_message(user):
    public_chat_message = user.create_public_chat_message('Test public message')
    assert public_chat_message.message_type == 'public_chat'
    assert public_chat_message.data == {
        'type': 'public_chat',
        'sender': 'mock_fingerprint',
        'message': 'Test public message'
    }
    assert public_chat_message.counter == 1

def test_create_client_list_request(user):
    client_list_request = user.create_client_list_request()
    assert client_list_request.message_type == 'client_list_request'
    assert client_list_request.data == {}
    assert client_list_request.counter == 1

def test_receive_message_chat(user, mock_message):
    mock_message.message_type = 'chat'
    mock_message.data = {
        'symm_keys': ['mock_encrypted_key'],
        'iv': base64.b64encode(b'mock_iv').decode('utf-8'),
        'chat': base64.b64encode(b'mock_encrypted_chat').decode('utf-8')
    }
    result = user.receive_message(mock_message)
    assert result == {"mock": "decrypted_data"}

def test_receive_message_public_chat(user, mock_message):
    mock_message.message_type = 'public_chat'
    mock_message.data = {
        'type': 'public_chat',
        'sender': 'mock_sender',
        'message': 'Test public message'
    }
    result = user.receive_message(mock_message)
    assert result == mock_message.data

def test_receive_message_client_list(user, mock_message):
    mock_message.message_type = 'client_list'
    mock_message.data = {
        'type': 'client_list',
        'servers': [{'address': 'test_server.com', 'clients': ['client1', 'client2']}]
    }
    result = user.receive_message(mock_message)
    assert result == mock_message.data

def test_receive_message_invalid_signature(user, mock_message):
    mock_message.verify.return_value = False
    with pytest.raises(ValueError, match="Message signature verification failed"):
        user.receive_message(mock_message)

def test_receive_message_invalid_counter(user, mock_message):
    mock_message.verify_counter.return_value = False
    with pytest.raises(ValueError, match="Message counter verification failed"):
        user.receive_message(mock_message)

def test_receive_message_unknown_type(user, mock_message):
    mock_message.message_type = 'unknown'
    with pytest.raises(ValueError, match="Unknown message type: unknown"):
        user.receive_message(mock_message)