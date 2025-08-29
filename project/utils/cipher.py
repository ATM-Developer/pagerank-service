import json
import hashlib
import base64

def encrypt_json(data, date, domain):
    """Encrypt JSON data and return encrypted string"""
    # Generate key
    key = hashlib.sha256(f"{date}_{domain}".encode()).digest()
    
    # Convert to JSON string
    json_str = json.dumps(data)
    json_bytes = json_str.encode('utf-8')
    
    # XOR encrypt
    encrypted = bytearray()
    for i, byte in enumerate(json_bytes):
        encrypted.append(byte ^ key[i % len(key)])
    
    # Return base64 encoded
    return base64.b64encode(encrypted).decode('utf-8')

def decrypt_json(encrypted_data, date, domain):
    """Decrypt encrypted string and return JSON data"""
    # Generate same key
    key = hashlib.sha256(f"{date}_{domain}".encode()).digest()
    
    # Decode from base64
    encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
    
    # XOR decrypt
    decrypted = bytearray()
    for i, byte in enumerate(encrypted_bytes):
        decrypted.append(byte ^ key[i % len(key)])
    
    # Convert back to JSON
    json_str = decrypted.decode('utf-8')
    return json.loads(json_str)


def encrypt_file_inplace(file_path, date, domain):
    """
    Read a JSON file, encrypt using encrypt_json(), overwrite file with encrypted text.
    """
    with open(file_path, "r") as f:
        data = json.load(f)

    encrypted = encrypt_json(data, date.replace('-', ''), domain)

    # overwrite same file with encrypted string
    with open(file_path, "w") as f:
        f.write(encrypted)


def decrypt_file_inplace(file_path, date, domain):
    """
    Read encrypted file, decrypt using decrypt_json(), overwrite file back with JSON.
    """
    with open(file_path, "r") as f:
        encrypted = f.read()

    data = decrypt_json(encrypted, date.replace('-', ''), domain)

    # overwrite same file with pretty JSON text
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

