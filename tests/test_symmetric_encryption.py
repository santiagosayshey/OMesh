# tests/test_symmetric_encryption.py

import unittest
from common.crypto import generate_aes_key, generate_iv, encrypt_aes_gcm, decrypt_aes_gcm

class TestSymmetricEncryption(unittest.TestCase):
    def test_aes_gcm_encryption_decryption(self):
        """
        Test: Fast Message Encryption
        Confirms that messages can be quickly encrypted and decrypted.
        Expected Outcome: The decrypted message matches the original message.
        """
        key = generate_aes_key()
        iv = generate_iv()
        message = b"Test message for AES-GCM encryption."

        # Encrypt the message
        ciphertext, tag = encrypt_aes_gcm(message, key, iv)

        # Decrypt the message
        plaintext = decrypt_aes_gcm(ciphertext, key, iv, tag)

        self.assertEqual(
            plaintext, message,
            "Decrypted plaintext does not match the original message."
        )

        # Print actual results
        print("Actual Result: Decrypted message matches the original message.")

    def test_decryption_with_incorrect_key(self):
        """
        Test: Decryption with Incorrect AES Key
        Ensures decryption fails with an incorrect key.
        Expected Outcome: Decryption fails with an incorrect AES key.
        """
        key1 = generate_aes_key()
        key2 = generate_aes_key()
        iv = generate_iv()
        message = b"Test message for AES-GCM encryption."

        # Encrypt the message with key1
        ciphertext, tag = encrypt_aes_gcm(message, key1, iv)

        # Attempt to decrypt with key2
        with self.assertRaises(Exception):
            decrypt_aes_gcm(ciphertext, key2, iv, tag)

        # Print actual results
        print("Actual Result: Decryption failed with incorrect AES key as expected.")

if __name__ == '__main__':
    unittest.main()
