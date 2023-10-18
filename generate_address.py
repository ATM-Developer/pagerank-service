
import os
import json
from web3 import Web3


def generate():
    password = os.getenv('ATMPD')

    w3 = Web3()
    account = w3.eth.account.create()
    keystore_data = account.encrypt(password)
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "keystore.json")
    with open(file_path, "w") as keystore_file:
        json.dump(keystore_data, keystore_file)

    print('wallet address: 0x{}'.format(keystore_data['address']))
    print("keystore.json file path: {}".format(file_path))
    print("Keystore file saved as 'keystore.json'. Make sure to back it up securely.")
    print("Place the keystore file in another directory, Do not place it in the project directory to avoid updating or deleting files.")


generate()
