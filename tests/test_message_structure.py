# tests/test_message_structure.py

import unittest
import json
import base64
from common.crypto import generate_rsa_key_pair, export_public_key, export_private_key
from common.protocol import (
    build_hello_message,
    build_chat_message,
    build_public_chat_message,
    build_client_list_request,
    build_client_update,
    build_client_update_request,
    build_server_hello,
    validate_message_format,
)
from cryptography.hazmat.primitives import serialization

class TestMessageStructureCompliance(unittest.TestCase):

    def setUp(self):
        # Generate RSA key pairs for testing
        self.private_key_sender, self.public_key_sender = generate_rsa_key_pair()
        self.private_key_recipient, self.public_key_recipient = generate_rsa_key_pair()
        self.sender_fingerprint = self._calculate_fingerprint(self.public_key_sender)
        self.recipient_fingerprint = self._calculate_fingerprint(self.public_key_recipient)
        self.destination_servers = ["server1"]
        self.recipients_public_keys = [self.public_key_recipient]
        self.counter = 1  # Initialize counter

    def _calculate_fingerprint(self, public_key):
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        fingerprint = base64.b64encode(public_pem).decode('utf-8')
        return fingerprint

    def test_hello_message_structure(self):
        """
        Test Case 7.1: Valid Hello Message
        Purpose: Ensure correct message format upon client connection.
        Expected Structure: Matches the protocol specification.
        """
        message = build_hello_message(self.public_key_sender, self.private_key_sender, self.counter)
        expected_structure = {
            "type": "signed_data",
            "data": {
                "type": "hello",
                "public_key": str,
            },
            "counter": int,
            "signature": str,
        }
        is_valid = self._compare_structure(message, expected_structure)
        self.assertTrue(
            is_valid,
            f"Hello message does not match expected structure.\nActual message:\n{json.dumps(message, indent=2)}"
        )
        if is_valid:
            print("Actual Result: Hello message matches the expected structure.")

    def test_hello_message_missing_public_key(self):
        """
        Test Case 7.2: Hello Message Missing Public Key
        Purpose: Ensure proper handling of malformed messages.
        Expected Result: Message validation fails due to missing 'public_key'.
        """
        message = build_hello_message(self.public_key_sender, self.private_key_sender, self.counter)
        # Remove 'public_key' field to simulate missing field
        del message['data']['public_key']
        is_valid = validate_message_format(message)
        self.assertFalse(
            is_valid,
            f"Message validation should fail due to missing 'public_key'.\nActual message:\n{json.dumps(message, indent=2)}"
        )
        if not is_valid:
            print("Actual Result: Message validation failed as expected due to missing 'public_key'.")

    def test_chat_message_structure(self):
        """
        Test Case 8.1: Valid Chat Message
        Purpose: Ensure correct structure and encryption of chat messages.
        Expected Structure: Matches the protocol specification.
        """
        message_text = "Hello, this is a test message."
        message = build_chat_message(
            self.destination_servers,
            self.recipients_public_keys,
            self.private_key_sender,
            self.counter,
            message_text
        )
        expected_structure = {
            "type": "signed_data",
            "data": {
                "type": "chat",
                "destination_servers": list,
                "iv": str,
                "symm_keys": list,
                "chat": str
            },
            "counter": int,
            "signature": str,
        }
        is_valid = self._compare_structure(message, expected_structure)
        self.assertTrue(
            is_valid,
            f"Chat message does not match expected structure.\nActual message:\n{json.dumps(message, indent=2)}"
        )
        if is_valid:
            print("Actual Result: Chat message matches the expected structure.")

    def test_chat_message_missing_symm_keys(self):
        """
        Test Case 8.2: Chat Message with Missing Fields
        Purpose: Ensure messages with missing or incorrect fields are rejected.
        Expected Result: Message validation fails due to missing 'symm_keys'.
        """
        message_text = "Hello, this is a test message."
        message = build_chat_message(
            self.destination_servers,
            self.recipients_public_keys,
            self.private_key_sender,
            self.counter,
            message_text
        )
        # Remove 'symm_keys' field to simulate missing field
        del message['data']['symm_keys']
        is_valid = validate_message_format(message)
        self.assertFalse(
            is_valid,
            f"Message validation should fail due to missing 'symm_keys'.\nActual message:\n{json.dumps(message, indent=2)}"
        )
        if not is_valid:
            print("Actual Result: Message validation failed as expected due to missing 'symm_keys'.")

    def test_public_chat_message_structure(self):
        """
        Test Case 9.1: Valid Public Chat Message
        Purpose: Ensure public chat messages are correctly formatted and broadcasted.
        Expected Structure: Matches the protocol specification.
        """
        message_text = "Hello everyone!"
        message = build_public_chat_message(
            self.public_key_sender,
            self.private_key_sender,
            self.counter,
            message_text
        )
        expected_structure = {
            "type": "signed_data",
            "data": {
                "type": "public_chat",
                "sender": str,
                "message": str
            },
            "counter": int,
            "signature": str,
        }
        is_valid = self._compare_structure(message, expected_structure)
        self.assertTrue(
            is_valid,
            f"Public chat message does not match expected structure.\nActual message:\n{json.dumps(message, indent=2)}"
        )
        if is_valid:
            print("Actual Result: Public chat message matches the expected structure.")

    def test_client_list_request_structure(self):
        """
        Test Case 10.1: Client List Request and Response
        Purpose: Ensure client list retrieval functions as specified.
        Expected Structure: Matches the protocol specification.
        """
        message = build_client_list_request()
        expected_structure = {
            "type": "client_list_request"
        }
        is_valid = self._compare_structure(message, expected_structure)
        self.assertTrue(
            is_valid,
            f"Client list request does not match expected structure.\nActual message:\n{json.dumps(message, indent=2)}"
        )
        if is_valid:
            print("Actual Result: Client list request message matches the expected structure.")

    def test_client_update_structure(self):
        """
        Test Case 11.1: Client Update Message
        Purpose: Ensure servers send 'client_update' messages appropriately.
        Expected Structure: Matches the protocol specification.
        """
        clients_public_keys = [self.public_key_sender, self.public_key_recipient]
        message = build_client_update(clients_public_keys)
        expected_structure = {
            "type": "client_update",
            "clients": list
        }
        is_valid = self._compare_structure(message, expected_structure)
        self.assertTrue(
            is_valid,
            f"Client update message does not match expected structure.\nActual message:\n{json.dumps(message, indent=2)}"
        )
        if is_valid:
            print("Actual Result: Client update message matches the expected structure.")

    def test_server_hello_structure(self):
        """
        Test Case 11.2: Server Hello Message
        Purpose: Ensure servers establish connections as per protocol.
        Expected Structure: Matches the protocol specification.
        """
        sender_address = "server1"
        self.counter += 1
        # Note: Adjusted to pass in private_key and counter
        message = build_server_hello(sender_address, self.private_key_sender, self.counter)
        expected_structure = {
            "type": "signed_data",
            "data": {
                "type": "server_hello",
                "sender": str
            },
            "counter": int,
            "signature": str,
        }
        is_valid = self._compare_structure(message, expected_structure)
        if is_valid:
            print("Actual Result: Server hello message matches the expected structure.")
        else:
            print(f"Actual Result: Server hello message does not match expected structure.\nActual message:\n{json.dumps(message, indent=2)}")
        self.assertTrue(
            is_valid,
            f"Server hello message does not match expected structure.\nActual message:\n{json.dumps(message, indent=2)}"
        )

    def _compare_structure(self, actual, expected):
        """
        Recursively compare the structure of the actual message with the expected structure.
        Types in expected can be:
        - dict: expects a dictionary
        - list: expects a list
        - type: expects a value of that type (e.g., int, str)
        """
        if isinstance(expected, type):
            return isinstance(actual, expected)
        elif isinstance(expected, dict):
            if not isinstance(actual, dict):
                print(f"Expected a dict at this level, but got {type(actual).__name__}")
                return False
            for key, value in expected.items():
                if key not in actual:
                    print(f"Missing key: {key}")
                    return False
                if not self._compare_structure(actual[key], value):
                    print(f"Mismatch at key: {key}")
                    return False
            return True
        elif isinstance(expected, list):
            if not isinstance(actual, list):
                print(f"Expected a list at this level, but got {type(actual).__name__}")
                return False
            if not actual:
                return True  # Empty list matches
            # Assume all items in the list should have the same structure
            expected_item = expected[0] if len(expected) > 0 else None
            for item in actual:
                if not self._compare_structure(item, expected_item):
                    return False
            return True
        else:
            # For expected literals (e.g., specific strings), compare directly
            return actual == expected
        
if __name__ == '__main__':
    unittest.main()
