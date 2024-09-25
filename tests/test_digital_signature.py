# tests/test_digital_signature.py

import unittest
from common.crypto import generate_rsa_key_pair, sign_data, verify_signature

class TestDigitalSignature(unittest.TestCase):
    def test_rsa_pss_signing_verification(self):
        """
        Test: Signing Messages
        Ensures messages can be signed to confirm the sender's identity.
        Expected Outcome: Signature verification succeeds with the correct key and fails with an incorrect key.
        """
        private_key, public_key = generate_rsa_key_pair()
        message = b"Test message for RSA-PSS signing."

        # Sign the message
        signature = sign_data(message, private_key)

        # Verify with correct public key
        is_valid_correct = verify_signature(message, signature, public_key)
        self.assertTrue(is_valid_correct, "Signature verification failed with the correct public key.")

        # Verify with incorrect public key
        _, wrong_public_key = generate_rsa_key_pair()
        is_valid_incorrect = verify_signature(message, signature, wrong_public_key)
        self.assertFalse(is_valid_incorrect, "Signature should not be valid with an incorrect public key.")

        # Print actual results
        print("Actual Result: Signature verified successfully with correct key; verification failed with incorrect key as expected.")

    def test_verification_of_modified_message(self):
        """
        Test: Verification of Modified Message
        Ensures message integrity is protected.
        Expected Outcome: Verification fails if the message is modified.
        """
        private_key, public_key = generate_rsa_key_pair()
        message = b"Original message."
        modified_message = b"Modified message."

        # Sign the original message
        signature = sign_data(message, private_key)

        # Attempt to verify the signature with the modified message
        is_valid = verify_signature(modified_message, signature, public_key)
        self.assertFalse(is_valid, "Signature should not be valid for modified message.")

        # Print actual results
        print("Actual Result: Verification failed for modified message as expected.")

if __name__ == '__main__':
    unittest.main()
