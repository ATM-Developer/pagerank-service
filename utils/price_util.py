import os
import time
import pytz
import json
import fcntl
import logging
import traceback
from web3 import Web3
from flask_apscheduler import APScheduler

from utils.config_util import params
from Configs.eth.eth_config import PRICE_ABI
from utils.eth_util import Web3Eth

logger = logging.getLogger('main')


class Price:
    def __init__(self):
        self.web3 = Web3(Web3.HTTPProvider(params.web3_provider_uri))

    def get(self, coin):
        try:
            if coin == 'WETH':
                contract = self.eth_contract()
            elif coin == 'WBTC':
                contract = self.btc_contract()
            elif coin == 'LINK':
                contract = self.link_contract()
            elif coin == 'BNB':
                contract = self.bnb_contract()
            elif coin == 'CAKE':
                contract = self.cake_contract()
            else:
                return None
            latestData = contract.functions.latestRoundData().call()
            decimals = contract.functions.decimals().call()
            price = latestData[1] / (10 ** decimals)
            logger.info('latestData: {}, decimals: {}, price: {}'.format(latestData, decimals, price))
            return price
        except:
            logger.error(traceback.format_exc())
            return None

    def eth_contract(self):
        contract = self.web3.eth.contract(address=params.ETH_USD_ADDRESS, abi=PRICE_ABI)
        return contract

    def btc_contract(self):
        contract = self.web3.eth.contract(address=params.BTC_USD_ADDRESS, abi=PRICE_ABI)
        return contract

    def link_contract(self):
        contract = self.web3.eth.contract(address=params.LINK_USD_ADDRESS, abi=PRICE_ABI)
        return contract

    def bnb_contract(self):
        contract = self.web3.eth.contract(address=params.BNB_USD_ADDRESS, abi=PRICE_ABI)
        return contract

    def cake_contract(self):
        contract = self.web3.eth.contract(address=params.CAKE_USD_ADDRESS, abi=PRICE_ABI)
        return contract


dir_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
if not os.path.exists(dir_path):
    try:
        os.makedirs(dir_path)
    except:
        pass


def get_coin_price():
    price = Price()
    coin_price = {}
    w3 = Web3Eth()
    luca_price = round(w3.get_luca_price(), 8)
    coin_price['LUCA'] = luca_price
    for i in ['WETH', 'WBTC', 'LINK', 'CAKE', 'BNB']:
        coin_price[i] = price.get(i)
    price_path = os.path.join(dir_path, 'coin_price.json')
    with open(price_path, 'w') as wf:
        wf.write(json.dumps(coin_price))
    return coin_price


try:
    print('Query Price Job Started')
    logger.info('Query Price Job Started')
    f = open(os.path.join(dir_path, 'f_lock.txt'), 'w')
    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    f.write(str(time.time()))
    apscheduler = APScheduler()
    apscheduler._scheduler.timezone = pytz.timezone('UTC')
    apscheduler.start()
    apscheduler.add_job(id='coin_price', func=get_coin_price, trigger='cron', hour=14)
    time.sleep(3)
    fcntl.flock(f, fcntl.LOCK_UN)
    f.close()
except:
    try:
        f.close()
    except:
        pass
    logger.error(traceback.format_exc())
