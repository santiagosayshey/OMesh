import argparse
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import requests

def get_password():
    url = "https://gist.githubusercontent.com/santiagosayshey/8ef85ea7f02eeb4897c6411c597496e9/raw"
    try:
        response = requests.get(url)
        return response.text.strip()
    except:
        print(f"Failed to retrieve password from {url}")
        return ''

def generate_key(password):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'static_salt',  # In practice, use a random salt
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key

def encrypt_file(file_path, password):
    with open(file_path, 'rb') as file:
        data = file.read()
    
    fernet = Fernet(generate_key(password))
    encrypted_data = fernet.encrypt(data)
    
    encrypted_file_path = file_path + '.encrypted'
    with open(encrypted_file_path, 'wb') as file:
        file.write(encrypted_data)
    
    print(f"Encrypted file saved as: {encrypted_file_path}")

def main():
    parser = argparse.ArgumentParser(description="Encrypt a file using a special password.")
    parser.add_argument("file", help="Path to the file to be encrypted")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' not found.")
        return

    print("Retrieving password...")
    print("Hint: The password is hidden in a GitHub Gist.")
    print("URL: https://gist.github.com/santiagosayshey/8ef85ea7f02eeb4897c6411c597496e9")
    print("What could this mystery password be?")
    
    password = get_password()
    
    if not password:
        print("Failed to retrieve the password. Encryption aborted.")
        return

    print("\nPassword retrieved. Now encrypting the file...")
    encrypt_file(args.file, password)
    
    print("\nEncryption complete!")
    print("To decrypt this file, you'll need to figure out the password.")
    print("Remember, the password is hidden in plain sight, spread across the web.")
    print("Good luck, and never give up on cracking this code!")

if __name__ == "__main__":
    main()