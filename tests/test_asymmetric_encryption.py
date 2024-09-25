# tests/test_asymmetric_encryption.py

import unittest
from common.crypto import generate_rsa_key_pair, encrypt_rsa_oaep, decrypt_rsa_oaep

class TestAsymmetricEncryption(unittest.TestCase):
    def test_rsa_oaep_encryption_decryption(self):
        """
        Test: Encrypting and Decrypting Messages
        Verifies that messages can be locked and unlocked properly.
        Expected Outcome: The decrypted message matches the original message.
        """
        private_key, public_key = generate_rsa_key_pair()
        message = b"Test message for RSA-OAEP encryption."

        # Encrypt the message
        ciphertext = encrypt_rsa_oaep(message, public_key)

        # Decrypt the message
        plaintext = decrypt_rsa_oaep(ciphertext, private_key)

        self.assertEqual(
            plaintext, message,
            "Decrypted plaintext does not match the original message."
        )

        # Print actual results
        print("Actual Result: Decrypted message matches the original message.")

    def test_decryption_with_incorrect_private_key(self):
        """
        Test: Decryption with Incorrect Private Key
        Ensures decryption fails when using an incorrect key.
        Expected Outcome: Decryption fails with an incorrect private key.
        """
        private_key1, public_key1 = generate_rsa_key_pair()
        private_key2, public_key2 = generate_rsa_key_pair()
        message = b"Test message for RSA-OAEP encryption."

        # Encrypt the message with public_key1
        ciphertext = encrypt_rsa_oaep(message, public_key1)

        # Attempt to decrypt with private_key2
        with self.assertRaises(Exception) as context:
            decrypt_rsa_oaep(ciphertext, private_key2)

        # Print actual results
        print("Actual Result: Decryption failed with incorrect private key as expected.")

if __name__ == '__main__':
    unittest.main()
