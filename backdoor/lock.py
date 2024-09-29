import argparse
import os
from cryptography.fernet import Fernet
import hashlib
import base64
import requests

def get_secret_lyrics():
    urls = [
        "https://gist.githubusercontent.com/xXShadowKillerXx/a1b2c3d4e5f6g7h8i9j0/raw/a1b2c3d4e5f6g7h8i9j0",
        "https://gist.githubusercontent.com/emily_rose/1234567890abcdef/raw/1234567890abcdef",
        "https://gist.githubusercontent.com/pogchamp420/abcdef123456/raw/abcdef123456",
        "https://gist.githubusercontent.com/uwu_uwu_uwu/f0e1d2c3b4a5/raw/f0e1d2c3b4a5",
        "https://gist.githubusercontent.com/dababy_yeah_yeah/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6/raw/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
        "https://gist.githubusercontent.com/coolbeans55/9876543210fedcba/raw/9876543210fedcba",
        "https://gist.githubusercontent.com/santiagosayshey/8ef85ea7f02eeb4897c6411c597496e9/raw",
        "https://gist.githubusercontent.com/catgirl_nyaa/123abc456def/raw/123abc456def",
        "https://gist.githubusercontent.com/sigma_grindset/abcdefghijklmnop/raw/abcdefghijklmnop",
        "https://gist.githubusercontent.com/zzz_sleepy_coder/a1b2c3/raw/a1b2c3",
        "https://gist.githubusercontent.com/gigachad9000/1a2b3c4d5e6f7g8h9i0j/raw/1a2b3c4d5e6f7g8h9i0j",
        "https://gist.githubusercontent.com/john_smith_1985/abc123def456ghi789/raw/abc123def456ghi789",
        "https://gist.githubusercontent.com/harambe_lives/abcdef1234567890/raw/abcdef1234567890",
        "https://gist.githubusercontent.com/sadge_pepe/a1b2c3d4e5/raw/a1b2c3d4e5",
        "https://gist.githubusercontent.com/amogus_sus/1234567890abcdef1234567890/raw/1234567890abcdef1234567890",
        "https://gist.githubusercontent.com/doge_to_the_moon/ab12cd34ef56/raw/ab12cd34ef56",
        "https://gist.githubusercontent.com/rawr_xd/123456abcdef/raw/123456abcdef",
        "https://gist.githubusercontent.com/karen_from_finance/1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t/raw/1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t",
        "https://gist.githubusercontent.com/xx_dragonslayer_xx/abcd1234/raw/abcd1234",
        "https://gist.githubusercontent.com/yolo_swaggins/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0/raw/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0"
    ]
    for url in urls:
        try:
            response = requests.get(url)
            if "never" in response.text.lower():
                return response.text.strip()
        except:
            pass
    return ''

def generate_key(password):
    salt = b'rickroll'
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return base64.urlsafe_b64encode(key)


def encrypt_file(file_path, password):
    with open(file_path, 'rb') as file:
        data = file.read()
    
    fernet = Fernet(generate_key(password))
    encrypted_data = fernet.encrypt(data)
    
    encrypted_file_path = file_path + '.encrypted'
    with open(encrypted_file_path, 'wb') as file:
        file.write(encrypted_data)

def decrypt_file(file_path, password):
    with open(file_path, 'rb') as file:
        data = file.read()
    
    fernet = Fernet(generate_key(password))
    decrypted_data = fernet.decrypt(data)
    
    decrypted_file_path = file_path.rsplit('.', 1)[0]
    with open(decrypted_file_path, 'wb') as file:
        file.write(decrypted_data)

def main():
    parser = argparse.ArgumentParser(description="Encrypt or decrypt a file using a special password.")
    parser.add_argument("action", choices=['encrypt', 'decrypt'], help="Action to perform")
    parser.add_argument("file", help="Path to the file to be processed")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' not found.")
        return

    password = input("Enter the password: ")
    
    if not password:
        print("Error: Password cannot be empty.")
        return

    try:
        if args.action == 'encrypt':
            encrypt_file(args.file, password)
            print(f"File encrypted successfully: {args.file}.encrypted")
        else:
            decrypt_file(args.file, password)
            print(f"File decrypted successfully: {args.file.rsplit('.', 1)[0]}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()