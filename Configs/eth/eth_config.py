import os
import json

current_path = os.path.dirname(__file__)

FACTORY_ADDRESS = '0x5140c0F48D4b3C25C79D71A7FE3E68a0a6C3302b'
with open(current_path + '/factory.abi') as j:
    FACTORY_ABI = json.load(j)

with open(current_path + '/link.abi') as j:
    LINK_ABI = json.load(j)

PLEDGE_ADDRESS = '0x27A1C0C6D4F1d2D5dF5CbA23499208f791209BF8'
with open(current_path + '/pledge.abi') as j:
    PLEDGE_ABI = json.load(j)
