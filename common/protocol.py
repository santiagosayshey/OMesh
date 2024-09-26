# common/protocol.py

import json
import base64
from common.crypto import (
    generate_aes_key,
    generate_iv,
    encrypt_aes_gcm,
    encrypt_rsa_oaep,
    calculate_fingerprint,
    sign_data,
    verify_signature
)
from enum import Enum
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
    # Prepare the payload for signing
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
def build_hello_message(public_key, private_key, counter):
    """
    Constructs a signed 'hello' message according to the protocol.
    """
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

    data_dict = {
        "type": "hello",
        "public_key": public_pem
    }
    return build_signed_message(data_dict, private_key, counter)

# Function to construct a 'chat' message
def build_chat_message(destination_servers, recipients_public_keys, sender_private_key, counter, message_text):
    # Generate AES key and IV
    aes_key = generate_aes_key()
    iv = generate_iv()
    iv_b64 = base64.b64encode(iv).decode('utf-8')

    # Prepare the chat data with wrapping 'chat' key
    sender_public_key = sender_private_key.public_key()
    sender_fingerprint = calculate_fingerprint(sender_public_key)
    participants = [sender_fingerprint] + [calculate_fingerprint(pk) for pk in recipients_public_keys]

    plaintext_chat_data = {
        "chat": {
            "participants": participants,
            "message": message_text
        }
    }
    chat_json = json.dumps(plaintext_chat_data)

    # Encrypt the chat data
    ciphertext, tag = encrypt_aes_gcm(chat_json.encode('utf-8'), aes_key, iv)
    chat_b64 = base64.b64encode(ciphertext + tag).decode('utf-8')

    # Encrypt AES key for each recipient
    symm_keys = []
    for public_key in recipients_public_keys:
        encrypted_key = encrypt_rsa_oaep(aes_key, public_key)
        encrypted_key_b64 = base64.b64encode(encrypted_key).decode('utf-8')
        symm_keys.append(encrypted_key_b64)

    # Construct the 'data' field
    data_dict = {
        "type": "chat",
        "destination_servers": destination_servers,
        "iv": iv_b64,
        "symm_keys": symm_keys,
        "chat": chat_b64
    }

    # Wrap the 'data' field in 'signed_data'
    signed_message = build_signed_message(data_dict, sender_private_key, counter)
    return signed_message

# Function to construct a 'public_chat' message
def build_public_chat_message(sender_public_key, sender_private_key, counter, message_text):
    sender_fingerprint = calculate_fingerprint(sender_public_key)
    data_dict = {
        "type": "public_chat",
        "sender": sender_fingerprint,
        "message": message_text
    }
    return build_signed_message(data_dict, sender_private_key, counter)

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
    - clients_public_keys: List of clients' public keys.
    """
    clients_pem = []
    for public_key in clients_public_keys:
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')  # Decode bytes to string
        clients_pem.append(public_pem)

    message = {
        "type": MessageType.CLIENT_UPDATE.value,
        "clients": clients_pem
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
def build_server_hello(sender_address, private_key, counter):
    data_dict = {
        "type": MessageType.SERVER_HELLO.value,
        "sender": sender_address
    }
    return build_signed_message(data_dict, private_key, counter)

# Function to validate the structure of a received message
def validate_message_format(message_dict):
    """
    Validates that the message has the required fields according to its type.
    Returns True if valid, False otherwise.
    """
    try:
        # Determine the message type
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
            # Check for required fields in the top-level message
            for field in required_fields:
                if field not in message_dict:
                    print(f"Validation Error: Message missing required field '{field}'.")
                    return False

            # Now check the nested 'data' field
            data = message_dict.get("data", {})
            if "type" not in data:
                print("Validation Error: Signed message 'data' missing 'type' field.")
                return False

            data_type = data["type"]
            if data_type == "hello":
                required_data_fields = ["type", "public_key"]
            elif data_type == "chat":
                required_data_fields = ["type", "destination_servers", "iv", "symm_keys", "chat"]
            elif data_type == "public_chat":
                required_data_fields = ["type", "sender", "message"]
            elif data_type == "server_hello":
                required_data_fields = ["type", "sender"]
            else:
                print(f"Validation Error: Unknown signed data type '{data_type}'.")
                return False

            for field in required_data_fields:
                if field not in data:
                    print(f"Validation Error: Signed message 'data' missing required field '{field}'.")
                    return False

        elif message_type == "client_list_request":
            required_fields = ["type"]
            for field in required_fields:
                if field not in message_dict:
                    print(f"Validation Error: Message missing required field '{field}'.")
                    return False

        elif message_type == "client_update":
            required_fields = ["type", "clients"]
            for field in required_fields:
                if field not in message_dict:
                    print(f"Validation Error: Message missing required field '{field}'.")
                    return False

        elif message_type == "client_list":
            required_fields = ["type", "servers"]
            for field in required_fields:
                if field not in message_dict:
                    print(f"Validation Error: Message missing required field '{field}'.")
                    return False

        elif message_type == "client_update_request":
            required_fields = ["type"]
            for field in required_fields:
                if field not in message_dict:
                    print(f"Validation Error: Message missing required field '{field}'.")
                    return False

        else:
            print(f"Validation Error: Unknown message type '{message_type}'.")
            return False

        return True
    except Exception as e:
        print(f"Validation Error: Exception occurred - {e}")
        return False
