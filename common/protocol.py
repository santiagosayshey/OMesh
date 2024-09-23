# common/protocol.py

import json
import base64
from enum import Enum
from collections import defaultdict
from common.crypto import sign_data, verify_signature, calculate_fingerprint
from cryptography.hazmat.primitives import serialization

# Enum for message types
class MessageType(Enum):
    SIGNED_DATA = "signed_data"
    CLIENT_LIST_REQUEST = "client_list_request"
    CLIENT_UPDATE = "client_update"
    CLIENT_LIST = "client_list"
    CLIENT_UPDATE_REQUEST = "client_update_request"
    SERVER_HELLO = "server_hello"
    HELLO = "hello"
    CHAT = "chat"
    PUBLIC_CHAT = "public_chat"


# Function to build a signed message
def build_signed_message(data_dict, private_key, counter):
    """
    Constructs a signed message according to the protocol.
    - data_dict: The 'data' field of the message.
    - private_key: Sender's RSA private key.
    - counter: Monotonically increasing counter value.
    """
    # Prepare the message payload
    payload = {
        "data": data_dict,
        "counter": counter
    }

    # Convert payload to JSON and then to bytes
    payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    payload_bytes = payload_json.encode('utf-8')

    # Sign the payload
    signature = sign_data(payload_bytes, private_key)
    signature_b64 = base64.b64encode(signature).decode('utf-8')

    # Construct the final message
    message = {
        "type": MessageType.SIGNED_DATA.value,
        "data": data_dict,
        "counter": counter,
        "signature": signature_b64
    }
    return message

# Function to verify a signed message
def verify_signed_message(message_dict, public_key, last_counter):
    """
    Verifies a signed message according to the protocol.
    - message_dict: The received message as a dictionary.
    - public_key: Sender's RSA public key.
    - last_counter: The last counter value received from this sender.
    Returns:
    - is_valid: Boolean indicating if the message is valid.
    - error: Error message if any.
    """
    try:
        # Check if message type is 'signed_data'
        if message_dict.get("type") != MessageType.SIGNED_DATA.value:
            return False, "Invalid message type"

        # Extract fields
        data_dict = message_dict.get("data")
        counter = message_dict.get("counter")
        signature_b64 = message_dict.get("signature")

        if data_dict is None or counter is None or signature_b64 is None:
            return False, "Missing required fields"

        # Check counter
        if counter <= last_counter:
            return False, "Replay attack detected (counter not greater than last)"

        # Prepare the payload for signature verification
        payload = {
            "data": data_dict,
            "counter": counter
        }
        payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        payload_bytes = payload_json.encode('utf-8')

        # Decode the signature
        signature = base64.b64decode(signature_b64.encode('utf-8'))

        # Verify signature
        is_valid = verify_signature(payload_bytes, signature, public_key)
        if not is_valid:
            return False, "Invalid signature"

        return True, None
    except Exception as e:
        return False, str(e)

# Utility function to parse incoming JSON messages
def parse_message(message_str):
    """
    Parses a JSON-formatted message string into a dictionary.
    """
    try:
        message_dict = json.loads(message_str)
        return message_dict, None
    except json.JSONDecodeError as e:
        return None, f"JSON decode error: {str(e)}"

# Function to construct a 'hello' message
def build_hello_message(public_key):
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    public_key_b64 = base64.b64encode(public_pem).decode('utf-8')

    data_dict = {
        "type": MessageType.HELLO.value,
        "public_key": public_key_b64
    }
    message = {
        "data": data_dict
    }
    return message



# Function to construct a 'chat' message
def build_chat_message(destination_servers, recipients_public_keys, sender_private_key, sender_counter, message_text):
    """
    Constructs an encrypted 'chat' message according to the protocol.
    - destination_servers: List of recipient server addresses.
    - recipients_public_keys: List of recipient public keys.
    - sender_private_key: Sender's RSA private key.
    - sender_counter: Sender's message counter.
    - message_text: Plaintext message to send.
    """
    from common.crypto import generate_aes_key, generate_iv, encrypt_aes_gcm, encrypt_rsa_oaep, calculate_fingerprint

    # Generate AES key and IV
    aes_key = generate_aes_key()
    iv = generate_iv()
    iv_b64 = base64.b64encode(iv).decode('utf-8')

    # Encrypt the message with AES-GCM
    plaintext_bytes = message_text.encode('utf-8')
    ciphertext, tag = encrypt_aes_gcm(plaintext_bytes, aes_key, iv)
    cipher_b64 = base64.b64encode(ciphertext + tag).decode('utf-8')  # Append tag to ciphertext

    # Encrypt AES key with recipients' public keys
    symm_keys = []
    participants = []
    destination_servers_list = []
    for public_key in recipients_public_keys:
        encrypted_key = encrypt_rsa_oaep(aes_key, public_key)
        encrypted_key_b64 = base64.b64encode(encrypted_key).decode('utf-8')
        symm_keys.append(encrypted_key_b64)
        # Calculate fingerprint
        fingerprint = calculate_fingerprint(public_key)
        participants.append(fingerprint)

    # Add sender's own fingerprint at the beginning
    sender_public_key = sender_private_key.public_key()
    sender_fingerprint = calculate_fingerprint(sender_public_key)
    participants.insert(0, sender_fingerprint)

    # Prepare the 'chat' data
    chat_data = {
        "participants": participants,
        "message": message_text  # Plaintext message is included in the encrypted 'chat' field
    }

    # Serialize 'chat' data
    chat_json = json.dumps(chat_data, separators=(',', ':'), sort_keys=True)
    # Note: In the protocol, the 'chat' field is supposed to be encrypted.

    # Build the 'data' field
    data_dict = {
        "type": MessageType.CHAT.value,
        "destination_servers": destination_servers,
        "iv": iv_b64,
        "symm_keys": symm_keys,
        "chat": cipher_b64
    }

    # Build the signed message
    message = build_signed_message(data_dict, sender_private_key, sender_counter)
    return message

# Function to construct a 'public_chat' message
def build_public_chat_message(sender_fingerprint, message_text):
    """
    Constructs a 'public_chat' message.
    - sender_fingerprint: Base64 encoded fingerprint of the sender.
    - message_text: Plaintext message to send.
    """
    data_dict = {
        "type": MessageType.PUBLIC_CHAT.value,
        "sender": sender_fingerprint,
        "message": message_text
    }
    message = {
        "data": data_dict
    }
    return message

# Function to construct a 'client_list_request' message
def build_client_list_request():
    """
    Constructs a 'client_list_request' message.
    """
    message = {
        "type": MessageType.CLIENT_LIST_REQUEST.value
    }
    return message

# Function to construct a 'client_update' message
def build_client_update(clients_public_keys):
    """
    Constructs a 'client_update' message.
    - clients_public_keys: List of clients' public keys in PEM format.
    """
    clients_b64 = []
    for public_key in clients_public_keys:
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        public_key_b64 = base64.b64encode(public_pem).decode('utf-8')
        clients_b64.append(public_key_b64)

    message = {
        "type": MessageType.CLIENT_UPDATE.value,
        "clients": clients_b64
    }
    return message

# Function to construct a 'client_update_request' message
def build_client_update_request():
    """
    Constructs a 'client_update_request' message.
    """
    message = {
        "type": MessageType.CLIENT_UPDATE_REQUEST.value
    }
    return message

# Function to construct a 'client_list' message (response from server)
def build_client_list(servers_clients_dict):
    """
    Constructs a 'client_list' message.
    - servers_clients_dict: Dictionary of servers and their clients.
    """
    message = {
        "type": MessageType.CLIENT_LIST.value,
        "servers": servers_clients_dict
    }
    return message

# Function to construct a 'server_hello' message
def build_server_hello(sender_address):
    data_dict = {
        "type": MessageType.SERVER_HELLO.value,
        "sender": sender_address
    }
    message = {
        "data": data_dict
    }
    return message



# Function to validate the structure of a received message
def validate_message_format(message_dict):
    """
    Validates that the message has the required fields according to its type.
    Returns True if valid, False otherwise.
    """
    if "type" in message_dict:
        message_type = message_dict["type"]
    elif "data" in message_dict and "type" in message_dict["data"]:
        message_type = message_dict["data"]["type"]
    else:
        print("Validation Error: Message missing 'type' field.")
        return False

    # Define required fields based on message_type
    if message_type == "signed_data":
        required_fields = ["data", "counter", "signature"]
    elif message_type == "client_list_request":
        required_fields = []
    elif message_type == "client_update":
        required_fields = ["clients"]
    elif message_type == "client_list":
        required_fields = ["servers"]
    elif message_type == "client_update_request":
        required_fields = []
    elif message_type == "hello":
        required_fields = ["data"]
    elif message_type == "server_hello":
        required_fields = ["data"]
    else:
        print(f"Validation Error: Unknown message type '{message_type}'.")
        return False

    # Check for required fields
    for field in required_fields:
        if field not in message_dict:
            print(f"Validation Error: Message missing required field '{field}'.")
            return False

    return True
