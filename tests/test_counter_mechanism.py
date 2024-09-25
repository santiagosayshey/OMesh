# tests/test_counter_mechanism.py

import unittest
from common.protocol import build_signed_message, verify_signed_message
from common.crypto import generate_rsa_key_pair

class TestCounterMechanism(unittest.TestCase):
    def test_counter_increments(self):
        """
        Test: Preventing Replay Attacks
        Verifies that old messages cannot be resent to trick users.
        Expected Outcome: Messages with increasing counters are accepted; messages with same or lower counters are rejected.
        """
        private_key, public_key = generate_rsa_key_pair()
        last_counter = 0

        # Test messages with increasing counters
        for counter in range(1, 6):
            data = {"type": "test_message", "content": "Test"}
            message = build_signed_message(data, private_key, counter)
            is_valid, error = verify_signed_message(message, public_key, last_counter)
            self.assertTrue(
                is_valid,
                f"Message with counter {counter} should be valid, but got error: {error}"
            )
            last_counter = counter

        # Test message with same counter
        data = {"type": "test_message", "content": "Test"}
        message = build_signed_message(data, private_key, last_counter)
        is_valid, error = verify_signed_message(message, public_key, last_counter)
        self.assertFalse(
            is_valid,
            "Message with same counter should be rejected."
        )

        # Test message with lower counter
        message = build_signed_message(data, private_key, last_counter - 1)
        is_valid, error = verify_signed_message(message, public_key, last_counter)
        self.assertFalse(
            is_valid,
            "Message with lower counter should be rejected."
        )

        # Print actual results
        print("Actual Result: Messages with increasing counters accepted; message with same or lower counter rejected as expected.")

if __name__ == '__main__':
    unittest.main()
