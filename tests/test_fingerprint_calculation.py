# tests/test_fingerprint_calculation.py

import unittest
from common.crypto import generate_rsa_key_pair, calculate_fingerprint, export_public_key
import hashlib

class TestFingerprintCalculation(unittest.TestCase):
    def test_public_key_fingerprint(self):
        """
        Test: Creating Unique IDs for Users
        Checks that each user gets a unique identifier.
        Expected Outcome: The fingerprint matches the SHA-256 hash of the public key.
        """
        private_key, public_key = generate_rsa_key_pair()

        # Manually calculate fingerprint
        public_pem = export_public_key(public_key)
        expected_fingerprint = hashlib.sha256(public_pem).hexdigest()

        # Use the function to calculate fingerprint
        calculated_fingerprint = calculate_fingerprint(public_key)

        self.assertEqual(
            calculated_fingerprint, expected_fingerprint,
            "Fingerprints do not match."
        )

        # Print actual results
        print("Actual Result: Fingerprint matches the SHA-256 hash of the public key.")

if __name__ == '__main__':
    unittest.main()
