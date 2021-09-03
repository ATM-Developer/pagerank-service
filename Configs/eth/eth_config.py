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

with open(current_path + '/price.abi') as f:
    PRICE_ABI = json.load(f)

LUCA_ADDRESS = '0xc172839154354e34a3Dd4768DdEc4C3e9c7C61D2'
with open(current_path + '/IERC20.abi') as j:
    IERC20_ABI = json.load(j)

USDC_ADDRESS = '0x4DBCdF9B62e891a7cec5A2568C3F4FAF9E8Abe2b'

LUCA_USDC_ADDRESS = '0x7a0B56C415e3A157179968252c67221606741dFE'

LUCA_DECIMALS = 18

USDC_DECIMALS = 6