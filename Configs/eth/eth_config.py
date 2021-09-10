import os
import json

current_path = os.path.dirname(__file__)

with open(current_path + '/factory.abi') as j:
    FACTORY_ABI = json.load(j)

with open(current_path + '/link.abi') as j:
    LINK_ABI = json.load(j)

with open(current_path + '/pledge.abi') as j:
    PLEDGE_ABI = json.load(j)

with open(current_path + '/price.abi') as f:
    PRICE_ABI = json.load(f)

with open(current_path + '/IERC20.abi') as j:
    IERC20_ABI = json.load(j)
