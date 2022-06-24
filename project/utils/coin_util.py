import os
import json
import time
import requests
import traceback
from web3 import Web3
from decimal import Decimal

from project.extensions import app_config
from project.configs.eth.eth_config import PRICE_ABI
from project.utils.eth_util import Web3Eth
from project.utils.date_util import get_pagerank_date, datetime_to_timestamp
from project.utils.settings_util import get_cfg
from project.utils.cache_util import CacheUtil

data_dir = get_cfg('setting', 'data_dir', path_join=True)


class Price:
    def __init__(self, logger, chain='binance'):
        self.logger = logger
        self.chain = chain
        self.get_web3eth()

    def get_web3eth(self):
        if self.chain == 'binance':
            uri = app_config.CHAINS['binance']['web3_provider_uri']
        else:
            uri = [app_config.INFURA_URI]
        for url in uri:
            self.web3 = Web3(Web3.HTTPProvider(url))
            if self.web3.isConnected():
                self._connected = True
                print('Selected URI: {}'.format(url))
                break
            else:
                continue

    def get(self, coin_usd_address):
        while True:
            try:
                contract = self.web3.eth.contract(address=coin_usd_address, abi=PRICE_ABI)
                latestData = contract.functions.latestRoundData().call()
                decimals = contract.functions.decimals().call()
                price = latestData[1] / (10 ** decimals)
                self.logger.info('latestData: {}, decimals: {}, price: {}'.format(latestData, decimals, price))
                return price
            except:
                self.logger.error(traceback.format_exc())
                self.get_web3eth()


def get_coin_price(logger, use_date):
    w3 = Web3Eth()
    price = Price(logger)
    coin_price = {}
    luca_price = round(w3.get_luca_price(), 8)
    coin_price['LUCA'] = luca_price
    for coin_name, coin_usd_address in app_config.COINS['binance'].items():
        coin_price[coin_name] = price.get(coin_usd_address)
        if coin_name == 'WBTC':
            coin_price['BTCB'] = coin_price['WBTC']
        elif coin_name == 'WETH':
            coin_price['ETH'] = coin_price['WETH']
    ethereum_price = Price(logger, 'ethereum')
    for coin_name, coin_usd_address in app_config.COINS['ethereum'].items():
        coin_price[coin_name] = ethereum_price.get(coin_usd_address)

    base_dir = os.path.join(data_dir, use_date)
    coin_list_file = os.path.join(base_dir, CacheUtil._COIN_LIST_FILE_NAME)
    with open(coin_list_file, 'r') as rf:
        coin_list = json.load(rf)
    for coin in coin_list['coinCurrencyPairList']:
        if coin['status'] == 1:
            continue
        if coin['baseCurrency'].upper() in coin_price:
            continue
        if coin['baseCurrency'].upper() == 'SCRT':
            coin_price[coin['baseCurrency'].upper()] = coin['nowPrice']
            continue
        if coin['aloneCalculateFlag'] != 1:
            symbol_price = round(w3.get_coin_price(coin['contractAddress'], coin['gateWay'], int(coin['weiPlaces'])), 8)
            coin_price[coin['baseCurrency'].upper()] = symbol_price
    logger.info('coin price: {}'.format(coin_price))
    return coin_price


def get_coin_list(logger):
    coin_list_url = app_config.COIN_LIST_URL
    coin_data1 = __request_coin_url(coin_list_url.format(1), logger)
    coin_data2 = __request_coin_url(coin_list_url.format(2), logger)
    backup_data = {'coinCurrencyPairList': []}
    # use yesterday data
    if coin_data1 is None or coin_data2 is None:
        cache_util = CacheUtil()
        logger.info('Read coin currency backup data: {}'.format(cache_util._yesterday_cache_date))
        backup_data = cache_util.get_cache_coin_list()
    coin_data = []
    if coin_data1:
        coin_data.extend(coin_data1)
    else:
        for i in backup_data['coinCurrencyPairList']:
            if i['chainId'] == 1:
                coin_data.append(i)
    if coin_data2:
        coin_data.extend(coin_data2)
    else:
        for i in backup_data['coinCurrencyPairList']:
            if i['chainId'] == 2:
                coin_data.append(i)

    return {"coinCurrencyPairList": coin_data}


def __request_coin_url(url, logger):
    coin_info = None
    for i in range(3):
        try:
            res = requests.get(url)
            logger.info('coin list info: {}'.format(res.text))
            result = json.loads(res.text)
            if result.get('success'):
                coin_info = result.get('data', {}).get('coinCurrencyPairList', [])
                break
            else:
                time.sleep(3)
        except:
            time.sleep(3)
    return coin_info


def luca_day_amount(logger):
    url = app_config.LUCA_DAY_AMOUNT_URL
    backup_data = {}
    for i in range(3):
        try:
            res = requests.get(url)
            logger.info('get luca day amount result : {}'.format(res.text))
            result = json.loads(res.text)
            if result.get('success'):
                backup_data = result.get('data', {})
                break
            else:
                time.sleep(3)
        except:
            logger.error(traceback.format_exc())
            time.sleep(3)
    # no backup data, use the data of yesterday
    if backup_data == {}:
        cache_util = CacheUtil()
        logger.info('Read luca amount backup data: {}'.format(cache_util._yesterday_cache_date))
        backup_data = CacheUtil().get_cache_luca_amount()
    return backup_data


def day_amount(logger):
    try:
        base_dir = os.path.join(data_dir, get_pagerank_date())
        luca_amount_file = os.path.join(base_dir, CacheUtil._LUCA_AMOUNT_FILE_NAME)
        coin_list_file = os.path.join(base_dir, CacheUtil._COIN_LIST_FILE_NAME)
        while True:
            if os.path.exists(luca_amount_file) and os.path.exists(coin_list_file):
                break
            time.sleep(1)
        with open(luca_amount_file, 'r') as rf:
            luca_amount = json.load(rf)

        pledge_reward, node_reward, pr_reward = \
            luca_amount.get('pledgeReward'), luca_amount.get('nodeReward'), luca_amount.get('prReward')
        liquidity_reward = luca_amount.get('liquidityReward')
        pledge_reward = pledge_reward if pledge_reward else 0
        node_reward = node_reward if node_reward else 0
        pr_reward = pr_reward if pr_reward else 0
        liquidity_reward = liquidity_reward if liquidity_reward else 0

        with open(coin_list_file, 'r') as rf:
            coin_list = json.load(rf)
        subcoin_rewards = {}
        for coin in coin_list['coinCurrencyPairList']:
            if coin['status'] == 1:
                continue
            if coin['aloneCalculateFlag'] in [2, 3]:
                coin_name = coin['currencyName'].lower()
                if coin['chainId'] == 2:
                    if '{}_net'.format(coin_name) in subcoin_rewards or '{}_alone'.format(coin_name) in subcoin_rewards:
                        continue
                subcoin_rewards['{}_net'.format(coin_name)] = coin['netRewardAmount']
                subcoin_rewards['{}_alone'.format(coin_name)] = coin['aloneRewardAmount']
        amounts = {
            'pledge_reward': pledge_reward,
            'node_reward': node_reward,
            'pr_reward': pr_reward,
            'liquidity_reward': liquidity_reward
        }
        amounts.update(subcoin_rewards)
        for k, v in amounts.items():
            amounts[k] = Decimal(str(v))
        return amounts
    except:
        logger.error(traceback.format_exc())
    return {}


def check_haved_earnings(file_path, web3eth=None):
    pagerank_date = get_pagerank_date()
    deadline_datetime = '{} {}:{}:00'.format(pagerank_date, app_config.START_HOUR, app_config.START_MINUTE)
    deadline_timestamp = datetime_to_timestamp(deadline_datetime)
    if web3eth is None:
        web3eth = Web3Eth()
    latest_proposal = web3eth.get_latest_snapshoot_proposal()
    if latest_proposal[5] < deadline_timestamp:
        return False
    if latest_proposal[-1] != 1:
        return False
    if not os.path.exists(file_path):
        return False
    return True
