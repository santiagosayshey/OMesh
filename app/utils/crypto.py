from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import os
import base64

class Crypto:
    AES_KEY_LENGTH = 32  # 256 bits

    @staticmethod
    def generate_rsa_key_pair():
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        public_key = private_key.public_key()
        return private_key, public_key

    @staticmethod
    def export_public_key(public_key):
        pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem.decode('utf-8')

    @staticmethod
    def rsa_encrypt(message, public_key):
        encrypted = public_key.encrypt(
            message,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.b64encode(encrypted).decode('utf-8')

    @staticmethod
    def rsa_decrypt(encrypted_message, private_key):
        decrypted = private_key.decrypt(
            base64.b64decode(encrypted_message),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return decrypted

    @staticmethod
    def rsa_sign(message, private_key):
        signature = private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=32  # As per the protocol specification
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')

    @staticmethod
    def rsa_verify(message, signature, public_key):
        try:
            public_key.verify(
                base64.b64decode(signature),
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=32
                ),
                hashes.SHA256()
            )
            return True
        except:
            return False

    @staticmethod
    def aes_encrypt(message, key):
        if len(key) != Crypto.AES_KEY_LENGTH:
            raise ValueError(f"AES key must be {Crypto.AES_KEY_LENGTH} bytes long")
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(message) + encryptor.finalize()
        ciphertext_with_tag = ciphertext + encryptor.tag
        return iv, ciphertext_with_tag

    @staticmethod
    def aes_decrypt(iv, ciphertext_with_tag, key):
        if len(key) != Crypto.AES_KEY_LENGTH:
            raise ValueError(f"AES key must be {Crypto.AES_KEY_LENGTH} bytes long")
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv))
        decryptor = cipher.decryptor()
        ciphertext = ciphertext_with_tag[:-16]
        tag = ciphertext_with_tag[-16:]
        decrypted_data = decryptor.update(ciphertext) + decryptor.finalize_with_tag(tag)
        return decrypted_data


    @staticmethod
    def generate_fingerprint(public_key):
        key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return base64.b64encode(hashes.Hash(hashes.SHA256()).update(key_bytes).finalize()).decode('utf-8')