import os
import json
import configparser
from web3 import Web3

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ENV_PATH = os.path.join(BASE_DIR, '.env')
ENV_LOADED = load_dotenv(ENV_PATH) if load_dotenv else False
cfg_path = os.path.join(BASE_DIR, 'project/settings.cfg')
config_parser = configparser.ConfigParser()
config_parser.read(cfg_path, encoding='utf-8')


def get_str(section, option, default=None, path_join=False):
    try:
        value = config_parser.get(section=section, option=option)
        if path_join:
            value = os.path.join(BASE_DIR, value)
    except:
        value = default
    return value


def get_int(section, option, default=None):
    try:
        value = config_parser.getint(section=section, option=option)
    except:
        value = default
    return value


def get_boolean(section, option, default=None):
    try:
        value = config_parser.getboolean(section=section, option=option)
    except:
        value = default
    return value


def get_float(section, option, default=None):
    try:
        value = config_parser.getfloat(section=section, option=option)
    except:
        value = default
    return value


def get_cfg(section, option, default=None, path_join=False):
    try:
        value = eval(config_parser.get(section=section, option=option))
        if path_join:
            value = os.path.join(BASE_DIR, value)
    except:
        value = default
    return value


def get_env_list(varname):
    # comma-separated list, e.g. PRIVATE_RPC_BINANCE=https://a,https://b
    value = os.getenv(varname)
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


def load_keystore(file_path):
    with open(file_path, "r") as keystore_file:
        keystore_data = json.load(keystore_file)
    password = os.getenv("ATMPD")
    w3 = Web3()
    private_key = w3.eth.account.decrypt(keystore_data, password).hex()
    address = '0x' + keystore_data['address']
    address = Web3.toChecksumAddress(address)
    return address, private_key[2:]
