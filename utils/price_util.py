import os
import time
import pytz
import json
import fcntl
import logging
import traceback
from flask_apscheduler import APScheduler

from utils.config_util import params
from Configs.eth.eth_config import PRICE_ABI
from utils.eth_util import Web3Eth
from utils.atm_util import AtmUtil
from http_helper import HttpHelper

logger = logging.getLogger('main')


class Price:
    def __init__(self):
        self.web3 = Web3Eth().get_w3()

    def get(self, coin_usd_address):
        try:
            contract = self.web3.eth.contract(address=coin_usd_address, abi=PRICE_ABI)
            latestData = contract.functions.latestRoundData().call()
            decimals = contract.functions.decimals().call()
            price = latestData[1] / (10 ** decimals)
            logger.info('latestData: {}, decimals: {}, price: {}'.format(latestData, decimals, price))
            return price
        except:
            logger.error(traceback.format_exc())
            return None


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
    for coin_name, coin_usd_address in params.Coins.items():
        coin_price[coin_name] = price.get(coin_usd_address)
        if coin_name == 'WBTC':
            coin_price['BTCB'] = coin_price['WBTC']
        elif coin_name == 'WETH':
            coin_price['ETH'] = coin_price['WETH']
    atm_util = AtmUtil(params.atmServer)
    http_helper = HttpHelper(params.centralServer)
    coin_info = atm_util.get_coin_list()
    if coin_info is None:
        print('Price Util: No coin info data from ATM, trying central server...')
        coin_info = http_helper.get_coin_list()
        if coin_info is None:
            print('Price Util: No coin info data from central server, can not calculate price, exit')
            return None
    for symbol, value in coin_info.items():
        if value['alone_calculate'] != 1:
            symbol_price = round(w3.get_coin_price(value['contract_address'], value['gateway'], value['decimals']), 8)
            coin_price[symbol] = symbol_price
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
    apscheduler.add_job(id='coin_price', func=get_coin_price, trigger='cron', hour=21)
    time.sleep(3)
    fcntl.flock(f, fcntl.LOCK_UN)
    f.close()
except:
    try:
        f.close()
    except:
        pass
    logger.error(traceback.format_exc())
