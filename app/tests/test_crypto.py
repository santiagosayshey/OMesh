import pytest
from ..utils.crypto import Crypto
from cryptography.hazmat.primitives.asymmetric import rsa

def test_generate_rsa_key_pair():
    print("Generating RSA key pair...")
    private_key, public_key = Crypto.generate_rsa_key_pair()
    print(f"Private key: {private_key}")
    print(f"Public key: {public_key}")
    assert isinstance(private_key, rsa.RSAPrivateKey)
    assert isinstance(public_key, rsa.RSAPublicKey)

def test_export_public_key():
    print("Testing export of public key...")
    _, public_key = Crypto.generate_rsa_key_pair()
    exported_key = Crypto.export_public_key(public_key)
    print(f"Exported key: {exported_key}")
    assert exported_key.startswith("-----BEGIN PUBLIC KEY-----")
    assert exported_key.endswith("-----END PUBLIC KEY-----\n")

def test_rsa_encrypt_decrypt():
    print("Testing RSA encryption and decryption...")
    private_key, public_key = Crypto.generate_rsa_key_pair()
    message = b"Hello, World!"
    encrypted = Crypto.rsa_encrypt(message, public_key)
    print(f"Encrypted message: {encrypted}")
    decrypted = Crypto.rsa_decrypt(encrypted, private_key)
    print(f"Decrypted message: {decrypted}")
    assert decrypted == message

def test_rsa_sign_verify():
    print("Testing RSA signing and verification...")
    private_key, public_key = Crypto.generate_rsa_key_pair()
    message = b"Hello, World!"
    signature = Crypto.rsa_sign(message, private_key)
    print(f"Signature: {signature}")
    assert Crypto.rsa_verify(message, signature, public_key)

def test_aes_encrypt_decrypt():
    print("Testing AES encryption and decryption...")
    key = b"0" * 32  # 256-bit key
    message = b"Hello, World!"
    encrypted = Crypto.aes_encrypt(message, key)
    print(f"Encrypted AES message: {encrypted}")
    decrypted = Crypto.aes_decrypt(encrypted, key)
    print(f"Decrypted AES message: {decrypted}")
    assert decrypted == message
