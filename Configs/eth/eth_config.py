import os
import json

current_path = os.path.dirname(__file__)

FACTORY_ADDRESS = '0x43131B80239bC6141064EB554C815823cCa5dE94'
with open(current_path + '/factory.abi') as j:
    FACTORY_ABI = json.load(j)

with open(current_path + '/link.abi') as j:
    LINK_ABI = json.load(j)

PLEDGE_ADDRESS = '0xc2510C2d00b648D35F4d83752C5B03991838429F'
with open(current_path + '/pledge.abi') as j:
    PLEDGE_ABI = json.load(j)
