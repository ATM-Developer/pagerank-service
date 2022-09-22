import os
import json
import time
import random
import requests
import traceback
from web3 import Web3
from decimal import Decimal

from project.extensions import app_config
from project.configs.eth.eth_config import PRICE_ABI
from project.utils.eth_util import Web3Eth
from project.utils.date_util import get_pagerank_date, datetime_to_timestamp, timestamp_to_format2
from project.utils.settings_util import get_cfg
from project.utils.cache_util import CacheUtil

data_dir = get_cfg('setting', 'data_dir', path_join=True)


class Price:
    def __init__(self, logger, cache_util, chain='binance'):
        self.logger = logger
        self.chain = chain
        self.uris = app_config.CHAINS[chain]['web3_provider_uri']
        self.cache_util = cache_util
        self.used_uri = []
        self.get_web3eth()

    def get_web3eth(self):
        for url in self.uris:
            try:
                if len(self.used_uri) == len(self.uris):
                    self.used_uri = []
                if url in self.used_uri:
                    continue
                self.web3 = Web3(Web3.HTTPProvider(url))
                self.used_uri.append(url)
                if self.web3.isConnected():
                    self._connected = True
                    self.logger.info('Selected URI: {}'.format(url))
                    break
                else:
                    self.logger.info('uri: {} not connect'.format(url))
                    continue
            except Exception as e:
                print(e)

    def get(self, coin_name, coin_usd_address, today_timestamp):
        time.sleep(random.randint(3, 20))
        times = 0
        while True:
            try:
                contract = self.web3.eth.contract(address=coin_usd_address, abi=PRICE_ABI)
                round_data = contract.functions.latestRoundData().call()
                self.logger.info('latestData: {}, {}'.format(round_data, timestamp_to_format2(round_data[-2])))
                if round_data[-2] > today_timestamp:
                    gt_updatedAt = round_data[-2]
                    gt_round_id = round_data[0]
                    interval = 1
                    while True:
                        lt_round_id = gt_round_id - interval
                        round_data = contract.functions.getRoundData(lt_round_id).call()
                        self.logger.info('round Data: {}, {}'.format(round_data, timestamp_to_format2(round_data[-2])))
                        if round_data[-2] <= today_timestamp:
                            break
                        interval = max(
                            int(interval / (gt_updatedAt - round_data[-2]) * (round_data[-2] - today_timestamp)), 1)
                        gt_round_id = lt_round_id
                        gt_updatedAt = round_data[-2]
                        time.sleep(random.randint(1, 2))
                    while True:
                        self.logger.info('round id gt: {}, lt:{}'.format(gt_round_id, lt_round_id))
                        middle_round_id = int((Decimal(gt_round_id) + Decimal(lt_round_id)) / 2)
                        round_data = contract.functions.getRoundData(middle_round_id).call()
                        self.logger.info('round Data: {}, {}'.format(round_data, timestamp_to_format2(round_data[-2])))
                        if round_data[-2] == today_timestamp:
                            break
                        if round_data[-2] > today_timestamp:
                            gt_round_id = middle_round_id
                            if gt_round_id - 1 == lt_round_id:
                                round_data = contract.functions.getRoundData(lt_round_id).call()
                                break
                        else:
                            lt_round_id = middle_round_id
                            if lt_round_id + 1 == gt_round_id:
                                break
                        time.sleep(random.randint(1, 2))
                decimals = contract.functions.decimals().call()
                price = round_data[1] / (10 ** decimals)
                self.logger.info('coin: {} latestData: {}, decimals: {}, price: {}'
                                 .format(coin_name, round_data, decimals, price))
                return price
            except:
                self.logger.error(traceback.format_exc())
                times += 1
                if times >=3 and coin_name == 'VET':
                    cache_coin_price = self.cache_util.get_cache_coin_price()
                    price = cache_coin_price['VET']
                    self.logger.info('coin: {}, cache price:{} '.format(coin_name, price))
                    return price
                time.sleep(random.randint(3, 12))
                self.get_web3eth()


def get_coin_price(logger, use_date, cache_util, w3):
    coin_price = {}
    luca_price = round(w3.get_luca_price(), 8)
    coin_price['LUCA'] = luca_price
    today_timestamp = datetime_to_timestamp('{} {}:{}:00'.format(use_date, app_config.OTHER_HOUR,
                                                                 app_config.OTHER_MINUTE))
    logger.info('today timestamp: {}'.format(today_timestamp))
    for chain, coin_info in app_config.COINS.items():
        price = Price(logger, cache_util, chain)
        for coin_name, coin_usd_address in coin_info.items():
            coin_price[coin_name] = price.get(coin_name, coin_usd_address, today_timestamp)
            if coin_name == 'WBTC':
                coin_price['BTCB'] = coin_price['WBTC']
            elif coin_name == 'WETH':
                coin_price['ETH'] = coin_price['WETH']

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


def get_coin_list(logger, cache_utl=None):
    coin_list_url = app_config.COIN_LIST_URL
    coin_datas = []
    for i in range(app_config.CHAIN_ID_NUMBER):
        coin_datas.append(__request_coin_url(coin_list_url.format(i + 1), logger))
    backup_data = {'coinCurrencyPairList': []}
    if None in coin_datas:
        cache_util = CacheUtil() if cache_utl is None else cache_utl
        logger.info('Read coin currency backup data: {}'.format(cache_util._yesterday_cache_date))
        backup_data = cache_util.get_cache_coin_list()
    coin_data = []
    for index, cds in enumerate(coin_datas):
        if cds:
            coin_data.extend(cds)
        else:
            for i in backup_data['coinCurrencyPairList']:
                if i['chainId'] == index + 1:
                    coin_data.append(i)
    # coin_data1 = __request_coin_url(coin_list_url.format(1), logger)
    # coin_data2 = __request_coin_url(coin_list_url.format(2), logger)
    # backup_data = {'coinCurrencyPairList': []}
    # # use yesterday data
    # if coin_data1 is None or coin_data2 is None:
    #     try:
    #         cache_util = CacheUtil()
    #         logger.info('Read coin currency backup data: {}'.format(cache_util._yesterday_cache_date))
    #         backup_data = cache_util.get_cache_coin_list()
    #     except Exception as e:
    #         logger.error('get coin list error: {}'.format(e))
    #         cache_util = CacheUtil(date_type='time')
    #         logger.info('Read coin currency backup data: {}'.format(cache_util._yesterday_cache_date))
    #         backup_data = cache_util.get_cache_coin_list()
    # coin_data = []
    # if coin_data1:
    #     coin_data.extend(coin_data1)
    # else:
    #     for i in backup_data['coinCurrencyPairList']:
    #         if i['chainId'] == 1:
    #             coin_data.append(i)
    # if coin_data2:
    #     coin_data.extend(coin_data2)
    # else:
    #     for i in backup_data['coinCurrencyPairList']:
    #         if i['chainId'] == 2:
    #             coin_data.append(i)

    return {'coinCurrencyPairList': coin_data}


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


def luca_day_amount(logger, cache_util):
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
        logger.info('Read luca amount backup data: {}'.format(cache_util._yesterday_cache_date))
        backup_data = cache_util.get_cache_luca_amount()
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


def check_haved_earnings(logger, file_path, web3eth=None):
    pagerank_date = get_pagerank_date()
    deadline_datetime = '{} {}:{}:00'.format(pagerank_date, app_config.START_HOUR, app_config.START_MINUTE)
    deadline_timestamp = datetime_to_timestamp(deadline_datetime)
    if web3eth is None:
        web3eth = Web3Eth(logger)
    latest_proposal = web3eth.get_latest_snapshoot_proposal()
    if latest_proposal[5] < deadline_timestamp:
        return False
    if latest_proposal[-1] != 1:
        return False
    if not os.path.exists(file_path):
        return False
    return True
