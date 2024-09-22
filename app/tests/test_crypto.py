import pytest
from utils.crypto import Crypto
from cryptography.hazmat.primitives.asymmetric import rsa

def test_generate_rsa_key_pair():
    private_key, public_key = Crypto.generate_rsa_key_pair()
    assert isinstance(private_key, rsa.RSAPrivateKey)
    assert isinstance(public_key, rsa.RSAPublicKey)

def test_export_public_key():
    _, public_key = Crypto.generate_rsa_key_pair()
    exported_key = Crypto.export_public_key(public_key)
    assert exported_key.startswith("-----BEGIN PUBLIC KEY-----")
    assert exported_key.endswith("-----END PUBLIC KEY-----\n")

def test_rsa_encrypt_decrypt():
    private_key, public_key = Crypto.generate_rsa_key_pair()
    message = b"Hello, World!"
    encrypted = Crypto.rsa_encrypt(message, public_key)
    decrypted = Crypto.rsa_decrypt(encrypted, private_key)
    assert decrypted == message

def test_rsa_sign_verify():
    private_key, public_key = Crypto.generate_rsa_key_pair()
    message = b"Hello, World!"
    signature = Crypto.rsa_sign(message, private_key)
    assert Crypto.rsa_verify(message, signature, public_key)

def test_aes_encrypt_decrypt():
    key = b"0" * 32  # 256-bit key
    message = b"Hello, World!"
    encrypted = Crypto.aes_encrypt(message, key)
    decrypted = Crypto.aes_decrypt(encrypted, key)
    assert decrypted == message