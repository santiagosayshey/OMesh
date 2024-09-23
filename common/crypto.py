# common/crypto.py

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric.padding import OAEP, MGF1, PSS
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature
import hashlib
import base64
import os

# Constants
RSA_KEY_SIZE = 2048
RSA_PUBLIC_EXPONENT = 65537
AES_KEY_SIZE = 32  # 256 bits
AES_IV_SIZE = 16   # 16 bytes
PSS_SALT_LENGTH = 32  # bytes


def generate_rsa_key_pair():
    """
    Generates an RSA key pair (private and public keys).
    Key size: 2048 bits
    Public exponent: 65537
    """
    private_key = rsa.generate_private_key(
        public_exponent=RSA_PUBLIC_EXPONENT,
        key_size=RSA_KEY_SIZE,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    return private_key, public_key


def load_public_key(pem_data):
    """
    Loads an RSA public key from PEM-encoded data.
    """
    public_key = serialization.load_pem_public_key(
        pem_data,
        backend=default_backend()
    )
    return public_key


def load_private_key(pem_data, password=None):
    """
    Loads an RSA private key from PEM-encoded data.
    If the key is encrypted, provide the password.
    """
    private_key = serialization.load_pem_private_key(
        pem_data,
        password=password,
        backend=default_backend()
    )
    return private_key


def sign_data(data_bytes, private_key):
    """
    Signs data using RSA-PSS with SHA-256.
    Salt length: 32 bytes
    """
    signature = private_key.sign(
        data_bytes,
        PSS(
            mgf=MGF1(hashes.SHA256()),
            salt_length=PSS_SALT_LENGTH
        ),
        hashes.SHA256()
    )
    return signature


def verify_signature(data_bytes, signature_bytes, public_key):
    """
    Verifies a signature using RSA-PSS with SHA-256.
    Returns True if the signature is valid, False otherwise.
    """
    try:
        public_key.verify(
            signature_bytes,
            data_bytes,
            PSS(
                mgf=MGF1(hashes.SHA256()),
                salt_length=PSS_SALT_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except InvalidSignature:
        return False


def encrypt_rsa_oaep(data_bytes, public_key):
    """
    Encrypts data using RSA-OAEP with SHA-256.
    """
    ciphertext = public_key.encrypt(
        data_bytes,
        OAEP(
            mgf=MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return ciphertext


def decrypt_rsa_oaep(cipher_bytes, private_key):
    """
    Decrypts data using RSA-OAEP with SHA-256.
    """
    plaintext = private_key.decrypt(
        cipher_bytes,
        OAEP(
            mgf=MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return plaintext


def encrypt_aes_gcm(plaintext_bytes, key_bytes, iv_bytes):
    """
    Encrypts data using AES-GCM.
    Key length: 32 bytes (256 bits)
    IV length: 16 bytes
    Returns the ciphertext and authentication tag.
    """
    encryptor = Cipher(
        algorithms.AES(key_bytes),
        modes.GCM(iv_bytes),
        backend=default_backend()
    ).encryptor()
    ciphertext = encryptor.update(plaintext_bytes) + encryptor.finalize()
    return ciphertext, encryptor.tag


def decrypt_aes_gcm(cipher_bytes, key_bytes, iv_bytes, tag):
    """
    Decrypts data using AES-GCM.
    Requires the ciphertext, key, IV, and authentication tag.
    """
    decryptor = Cipher(
        algorithms.AES(key_bytes),
        modes.GCM(iv_bytes, tag),
        backend=default_backend()
    ).decryptor()
    plaintext = decryptor.update(cipher_bytes) + decryptor.finalize()
    return plaintext


def calculate_fingerprint(public_key):
    """
    Calculates the fingerprint of a public key.
    Fingerprint = SHA-256(exported RSA public key in PEM format)
    """
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    fingerprint = hashlib.sha256(public_pem).hexdigest()
    return fingerprint


def export_public_key(public_key):
    """
    Exports a public key to PEM format.
    """
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return public_pem


def export_private_key(private_key, password=None):
    """
    Exports a private key to PEM format.
    If password is provided, the key will be encrypted using AES-256.
    """
    if password is not None:
        encryption_algorithm = serialization.BestAvailableEncryption(password)
    else:
        encryption_algorithm = serialization.NoEncryption()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption_algorithm
    )
    return private_pem


def generate_aes_key():
    """
    Generates a random AES key.
    Key length: 32 bytes (256 bits)
    """
    return os.urandom(AES_KEY_SIZE)


def generate_iv():
    """
    Generates a random initialization vector (IV) for AES-GCM.
    IV length: 16 bytes
    """
    return os.urandom(AES_IV_SIZE)
