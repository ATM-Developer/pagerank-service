import os
import json
from project.extensions import app_config

current_path = os.path.dirname(__file__)

with open(current_path + app_config.FACTORY_ABI) as j:
    FACTORY_ABI = json.load(j)

with open(current_path + app_config.LINK_ABI) as j:
    LINK_ABI = json.load(j)

with open(current_path + app_config.PLEDGE_ABI) as j:
    PLEDGE_ABI = json.load(j)

with open(current_path + app_config.PRICE_ABI) as f:
    PRICE_ABI = json.load(f)

with open(current_path + app_config.IERC20_ABI) as j:
    IERC20_ABI = json.load(j)

with open(current_path + app_config.INCENTIVE_ABI) as j:
    INCENTIVE_ABI = json.load(j)

with open(current_path + app_config.LUCA_ABI) as j:
    LUCA_ABI = json.load(j)

with open(current_path + app_config.CONF_ABI) as j:
    CONF_ABI = json.load(j)

with open(current_path + app_config.SENATOR_ABI) as j:
    SENATOR_ABI = json.load(j)

with open(current_path + app_config.POC_ABI) as j:
    POC_ABI = json.load(j)

with open(current_path + app_config.SNAPSHOOT_ABI) as j:
    SNAPSHOOT_ABI = json.load(j)

with open(current_path + app_config.LEDGER_ABI) as j:
    LEDGER_ABI = json.load(j)

with open(current_path + app_config.DRAW_PRIVATE_ABI) as j:
    DRAW_PRIVATE_ABI = json.load(j)

with open(current_path + app_config.NFT_FACTORY_ABI) as j:
    NFT_FACTORY_ABI = json.load(j)

with open(current_path + app_config.NFT_LINK_ABI) as j:
    NFT_LINK_ABI = json.load(j)
