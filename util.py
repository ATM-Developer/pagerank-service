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


class CalculateThread(threading.Thread):
    def __init__(self, threadID, name, counter, central_server_endpoint,
                 wallet_address, infura_url, cache_folder, output_folder):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter
        self.central_server_endpoint = central_server_endpoint
        self.wallet_address = wallet_address
        self.infura_url = infura_url
        self.cache_folder = cache_folder
        self.output_folder = output_folder
        self.http_helper = HttpHelper(central_server_endpoint)
        self.logger = logging.getLogger('calculate')

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
        pagerank_date = get_pagerank_date()
        date_str = pagerank_date.split('-')
        # deadline is 14 o'clock
        deadline_datetime = datetime(int(date_str[0]), int(date_str[1]), int(date_str[2]), 14, 0,
                                     tzinfo=pytz.timezone('UTC'))
        contract_deadline_timestamp = int(deadline_datetime.timestamp())
        # last transaction hash
        default_recent_transaction_hash_add = os.path.join(self.cache_folder, 'recent_transaction_hash.txt')
        if os.path.exists(default_recent_transaction_hash_add):
            with open(default_recent_transaction_hash_add, 'r') as f:
                h = f.read()
                last_block_number_yesterday = int(h.strip())
        else:
            last_block_number_yesterday = -1
        # prepare data
        data_reader = EthDataReader(self.infura_url)
        recorded, unrecorded, last_block_number_today = data_reader.prepare_data(
            contract_deadline_timestamp, last_block_number_yesterday)
        # load cache
        last_day_edge_multi_contract = os.path.join(self.cache_folder, 'last_day_edge_multi_contract.pickle')
        g = directed_graph()
        if os.path.exists(last_day_edge_multi_contract):
            g.load_info(last_day_edge_multi_contract)
        # check recorded data
        g.everyday_check_isAward(recorded)
        # g.everyday_time_last_effect()
        # add unrecorded data
        for i in unrecorded:
            g.build_from_new_transction(i)
        # generate results
        add2pr, importance_dict = g.generate_api_info()
        # save results
        g.save_info(os.path.join(self.output_folder, 'last_day_edge_multi_contract_' + pagerank_date + '.pickle'))
        if not os.path.exists(self.output_folder):
            os.mkdir(self.output_folder)
        with open(os.path.join(self.output_folder, 'pagerank_result_' + pagerank_date + '.json'), 'w') as f:
            json.dump(add2pr, f)
        with open(os.path.join(self.output_folder, 'importance_result_' + pagerank_date + '.json'), 'w') as f:
            json.dump(importance_dict, f)
        recorded_list = list(recorded)
        recorded_list.sort()
        recorded_list.extend(unrecorded)
        with open(os.path.join(self.output_folder, 'input_data_' + pagerank_date + '.pickle'), 'wb') as f:
            pickle.dump(recorded_list, f)
        with open(default_recent_transaction_hash_add, 'w') as f:
            f.write(str(last_block_number_today))

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
            self.calculate()
            print('Notifying...')
            self.logger.info('Notifying...')
            self.notify_completion()
            print('Done')
            self.logger.info('Done')
        except:
            self.logger.error(traceback.format_exc())
