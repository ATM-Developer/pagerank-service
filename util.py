from datetime import datetime, timedelta
import json
import pytz
from network import directed_graph
import os
import pickle
from reader import prepare_data, split_by_if_recorded
import threading
from http_helper import HttpHelper


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
        tz = pytz.timezone('Asia/Shanghai')
        bjTime = datetime.now(tz)
        if (bjTime >= datetime(bjTime.year, bjTime.month, bjTime.day, 22, 15, tzinfo=tz)):
            short_date = bjTime.strftime('%Y-%m-%d')
        else:
            short_date = (bjTime + timedelta(days=-1)).strftime('%Y-%m-%d')
        transactionHash_list, info_list = prepare_data(self.infura_url)
        default_recent_transaction_hash_add = os.path.join(
            self.cache_folder, 'recent_transaction_hash.txt')
        recorded, unrecorded = split_by_if_recorded(
            transactionHash_list, info_list, default_recent_transaction_hash_add)

        last_day_edge_multi_contract = os.path.join(
            self.cache_folder, 'last_day_edge_multi_contract.pickle')
        g = directed_graph()
        if os.path.exists(last_day_edge_multi_contract):
            g.load_info(last_day_edge_multi_contract)
        # 对recorded进行check isAward
        g.everyday_check_isAward(recorded)
        g.everyday_time_last_effect()
        # 对unrecorded录入网络
        for i in unrecorded:
            g.build_from_new_transction(i)

        add2pr, importance_dict = g.generate_api_info()
        g.save_info(os.path.join(self.output_folder,
                                 'last_day_edge_multi_contract_' + short_date + '.pickle'))

        # 保存数据
        _dir = 'output'
        if not os.path.exists(_dir):
            os.mkdir(_dir)
        with open(os.path.join(_dir, 'pagerank_result_' + short_date + '.json'), 'w') as f:
            json.dump(add2pr, f)

        with open(os.path.join(_dir, 'importance_result_' + short_date + '.json'), 'w') as f:
            json.dump(importance_dict, f)

        # 保存计算pagerank的原始数据
        # 格式：list of info_dict
        # with open('input_data.pkl', 'rb') as f:
        #     data = pickle.load(f)

        with open(os.path.join(_dir, 'input_data_' + short_date + '.pickle'), 'wb') as f:
            pickle.dump(info_list, f)

    def notify_completion(self):
        self.http_helper.notify_completion(self.wallet_address)

    def run(self):
        print('Clean Data...')
        self.clean_data()
        print('Get Cache Data...')
        self.get_lastday_cache()
        print('Calculating...')
        self.calculate()
        print('Notifying...')
        self.notify_completion()
