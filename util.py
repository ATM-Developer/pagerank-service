import os
import json
import pytz
import pickle
import logging
import threading
import traceback
from datetime import datetime
from http_helper import HttpHelper
from network import directed_graph
from utils.date_util import get_pagerank_date
from reader import EthDataReader
from utils.atm_util import AtmUtil
from utils.config_util import params


class CalculateThread(threading.Thread):
    def __init__(self, threadID, name, counter, central_server_endpoint, atm_url,
                 wallet_address, cache_folder, output_folder):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter
        self.central_server_endpoint = central_server_endpoint
        self.atm_url = atm_url
        self.wallet_address = wallet_address
        self.cache_folder = cache_folder
        self.output_folder = output_folder
        self.http_helper = HttpHelper(central_server_endpoint)
        self.logger = logging.getLogger('calculate')
        self.coins = {}

    def clean_data(self):
        if os.path.exists(self.cache_folder):
            for file in os.listdir(self.cache_folder):
                os.remove(os.path.join(self.cache_folder, file))
        else:
            os.makedirs(self.cache_folder)
        if os.path.exists(self.output_folder):
            for file in os.listdir(self.output_folder):
                os.remove(os.path.join(self.output_folder, file))
        else:
            os.makedirs(self.output_folder)

    def get_lastday_cache(self):
        self.http_helper.get_lastday_cache(self.cache_folder)

    def calculate(self):
        # query coin price and weight
        atm_util = AtmUtil(self.atm_url)
        coin_info = atm_util.get_coin_list()
        if coin_info is None:
            self.logger.error('No coin info data from ATM, trying central server...')
            coin_info = self.http_helper.get_coin_list()
            if coin_info is None:
                self.logger.error('No coin info data from central server, can not calculate PR, exit')
                return False
        link_rate = atm_util.get_link_rate()
        if link_rate is None:
            self.logger.error('No link rate data from ATM, trying central server...')
            link_rate = self.http_helper.get_link_rate()
            if link_rate is None:
                self.logger.error('No link rate data, can not calculate PR, exit')
                return False
        if os.path.exists('data/coin_price.json'):
            with open('data/coin_price.json', 'r') as f:
                coin_price = json.load(f)
                for key, value in coin_info.items():
                    if key in coin_price:
                        coin_info[key]['price'] = coin_price[key]
                    else:
                        self.logger.error('No price info for {}, can not calculate PR, exit'.format(key))
                        return False
        else:
            self.logger.error('No coin price data, can not calculate PR, exit')
            return False
        # prepare date
        pagerank_date = get_pagerank_date()
        date_str = pagerank_date.split('-')
        # deadline is 21 o'clock(UTC)
        deadline_datetime = datetime(int(date_str[0]), int(date_str[1]), int(date_str[2]), 21, 0,
                                     tzinfo=pytz.timezone('UTC'))
        contract_deadline_timestamp = int(deadline_datetime.timestamp())
        # block info yesterday
        default_recent_transaction_hash_add = os.path.join(self.cache_folder, 'recent_transaction_hash.txt')
        if os.path.exists(default_recent_transaction_hash_add):
            with open(default_recent_transaction_hash_add, 'r') as f:
                last_block_info_yesterday = json.load(f)
                if not isinstance(last_block_info_yesterday, dict):
                    # handle last version file
                    if isinstance(last_block_info_yesterday, int):
                        try:
                            last_block_info_yesterday = {
                                'binance': last_block_info_yesterday
                            }
                            for chain_name, chain_info in params.Chains.items():
                                if chain_name not in last_block_info_yesterday:
                                    last_block_info_yesterday[chain_name] = chain_info.get('FIRST_BLOCK')
                        except:
                            self.logger.error('Invalid config, exit')
                            return False
                    else:
                        self.logger.error('Invalid recent_transaction_hash.txt, exit')
                        return False
                else:
                    for chain_name, chain_info in params.Chains.items():
                        if chain_name not in last_block_info_yesterday:
                            last_block_info_yesterday[chain_name] = chain_info.get('FIRST_BLOCK')
        else:
            last_block_info_yesterday = {}
            for chain_name, chain_info in params.Chains.items():
                last_block_info_yesterday[chain_name] = chain_info.get('FIRST_BLOCK')
        # prepare data
        recorded = []
        unrecorded = []
        last_block_info_today = {}
        for chain_name, last_block_number_yesterday in last_block_info_yesterday.items():
            data_reader = EthDataReader(chain=chain_name)
            _recorded, _unrecorded, _last_block_number_today = data_reader.prepare_data(
                contract_deadline_timestamp, last_block_number_yesterday)
            recorded.extend(_recorded)
            unrecorded.extend(_unrecorded)
            last_block_info_today[chain_name] = _last_block_number_today
        # load cache
        last_day_edge_multi_contract = os.path.join(self.cache_folder, 'last_day_edge_multi_contract.pickle')

        if os.path.exists(last_day_edge_multi_contract):
            g = directed_graph(contract_deadline_timestamp, coin_info, link_rate)
            g.load_info(last_day_edge_multi_contract)
        else:
            g = directed_graph(contract_deadline_timestamp, coin_info, link_rate)
        # remove recorded data which has been rescinded
        g.remove_transactions(recorded)
        # add unrecorded data
        for i in unrecorded:
            g.build_from_new_transaction(i)
        # generate results
        add2pr, importance_dict = g.generate_api_info()
        # generate individual pr for special coins
        individual_pr = {}
        for key, value in coin_info.items():
            if coin_info[key]['alone_calculate'] == 2:
                coin_pr = g.generate_pr_info(key)
                individual_pr[key] = coin_pr
            else:
                pass
        # save results
        g.save_info(os.path.join(self.output_folder, 'last_day_edge_multi_contract_' + pagerank_date + '.pickle'))
        if not os.path.exists(self.output_folder):
            os.mkdir(self.output_folder)
        with open(os.path.join(self.output_folder, 'pagerank_result_' + pagerank_date + '.json'), 'w') as f:
            json.dump(add2pr, f)
        with open(os.path.join(self.output_folder, 'individual_pagerank_result_' + pagerank_date + '.json'), 'w') as f:
            json.dump(individual_pr, f)
        with open(os.path.join(self.output_folder, 'importance_result_' + pagerank_date + '.json'), 'w') as f:
            json.dump(importance_dict, f)
        recorded.extend(unrecorded)
        with open(os.path.join(self.output_folder, 'input_data_' + pagerank_date + '.pickle'), 'wb') as f:
            pickle.dump(recorded, f)
        with open(os.path.join(self.output_folder, 'recent_transaction_hash_' + pagerank_date + '.txt'), 'w') as f:
            json.dump(last_block_info_today, f)
        return True

    def notify_completion(self):
        self.http_helper.notify_completion(self.wallet_address)

    def run(self):
        try:
            print('Clean Data...')
            self.logger.info('Clean Data...')
            self.clean_data()
            print('Get Cache Data...')
            self.logger.info('Get Cache Data...')
            self.get_lastday_cache()
            print('Calculating...')
            self.logger.info('Calculating...')
            success = self.calculate()
            if success:
                print('Notifying...')
                self.logger.info('Notifying...')
                self.notify_completion()
                print('Done')
                self.logger.info('Done')
        except:
            self.logger.error(traceback.format_exc())
