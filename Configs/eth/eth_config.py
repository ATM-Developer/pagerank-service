import os
import json

current_path = os.path.dirname(__file__)

FACTORY_ADDRESS = '0xf3Ba58fB6E9e557D627f3EE84bf42b7aC0cff00E'
with open(current_path + '/factory.abi') as j:
    FACTORY_ABI = json.load(j)

with open(current_path + '/link.abi') as j:
    LINK_ABI = json.load(j)

PLEDGE_ADDRESS = '0xD3e381BBD05FC4B56dd58E69F3011B6fB89448Dd'
with open(current_path + '/pledge.abi') as j:
    PLEDGE_ABI = json.load(j)
