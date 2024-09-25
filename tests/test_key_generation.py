# tests/test_key_generation.py

import unittest
from common.crypto import generate_rsa_key_pair
from cryptography.hazmat.primitives.asymmetric import rsa

class TestKeyGeneration(unittest.TestCase):
    def test_rsa_key_pair_generation(self):
        """
        Test: Generating Secure Keys
        Checks if the system can create secure keys for encryption.
        Expected Outcome: The system generates a key with a modulus length of 2048 bits and a public exponent of 65537.
        """
        private_key, public_key = generate_rsa_key_pair()

        # Check modulus length (n)
        n = private_key.private_numbers().public_numbers.n
        modulus_length = n.bit_length()
        self.assertEqual(
            modulus_length, 2048,
            f"Modulus length is {modulus_length} bits, expected 2048 bits."
        )

        # Check public exponent (e)
        e = private_key.private_numbers().public_numbers.e
        self.assertEqual(
            e, 65537,
            f"Public exponent is {e}, expected 65537."
        )

        # Print actual results
        print(f"Actual Result: Modulus length is {modulus_length} bits, public exponent is {e}.")

if __name__ == '__main__':
    unittest.main()
