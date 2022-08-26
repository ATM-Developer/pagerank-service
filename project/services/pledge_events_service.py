import os
import json
import time
import traceback

from project.extensions import app_config
from project.models.entity import TbUserPledge
from project.configs.eth.eth_config import PLEDGE_ABI
from project.utils.eth_util import Web3Eth
from project.utils.settings_util import get_cfg
from project.utils.date_util import time_format, datetime_to_timestamp, get_pagerank_date
from project.utils.tar_util import TarUtil
from project.utils.cache_util import CacheUtil
from project.utils.helper_util import download_ipfs_file
from project.utils.data_util import SaveData
from project.services.blockchain_service import get_yesterday_file_id
from project.services.ipfs_service import IPFS


class Handler():
    def __init__(self, chain, logger):
        self.logger = logger
        self.chain = chain
        self.pledge_address = app_config.CHAINS[self.chain]['PLEDGE_ADDRESS']
        self.interval = app_config.CHAINS[self.chain]['INTERVAL']
        self.block_interval = app_config.CHAINS[self.chain]['BLOCK_INTERVAL']
        self.logger.info('{} {} {}'.format(self.pledge_address, self.interval, self.block_interval))
        self.web3eth = Web3Eth(self.logger, self.chain)
        self.start_block_number = 0
        self.end_block_number = 0
        self.items = []
        self.now_datetime = time_format()
        self.data_end_hour = app_config.DATA_END_HOUR
        self.data_end_minute = app_config.DATA_END_MINUTE
        self.other_hour = app_config.OTHER_HOUR
        self.other_minute = app_config.OTHER_MINUTE

    def __prepare_dir(self):
        self.data_dir = get_cfg('setting', 'data_dir', path_join=True)
        self.pledge_data_dir = os.path.join(self.data_dir, 'pledge_data')
        self.today_date = self.now_datetime[:10]
        self.tomorrow_date = time_format(timedeltas={'days': 1}, opera=1)[:10]
        if not os.path.exists(self.pledge_data_dir):
            os.makedirs(self.pledge_data_dir)
        self.block_number_file_path = os.path.join(self.pledge_data_dir, '{}_block_number.txt'.format(self.chain))
        self.tomorrow_data_file = os.path.join(self.pledge_data_dir, '{}_{}.txt'.format(self.chain, self.tomorrow_date))
        self.today_data_file = os.path.join(self.pledge_data_dir, '{}_{}.txt'.format(self.chain, self.today_date))
        return True

    def __download_yesterday(self, pagerank_date):
        self.logger.info('download yesterday data:')
        with open(self.block_number_file_path, 'w') as wf:
            json.dump({'is_run': True}, wf)
        file_id = get_yesterday_file_id(self.logger,
                                        datetime_to_timestamp('{} {}:{}:00'.format(pagerank_date, app_config.START_HOUR,
                                                                                   app_config.START_MINUTE)))
        file_name = '{}.tar.gz'.format(pagerank_date)
        ipfs = IPFS(self.logger)
        return download_ipfs_file(ipfs, self.data_dir, file_id, file_name, self.logger, TarUtil)

    def use_yesterday_block_num(self):
        # use ipfs block_num
        pagerank_date = get_pagerank_date()
        yesterday_block_number_file_path = os.path.join(self.data_dir, pagerank_date,
                                                        CacheUtil._PLEDGE_BLOCK_NUMBER_FILE_NAME)
        if not os.path.exists(yesterday_block_number_file_path):
            # download ipfs yesterday data
            if not self.__download_yesterday(pagerank_date):
                self.logger.info('failed to download yesterday data.')
                return False
        with open(yesterday_block_number_file_path, 'r') as rf:
            block_data = json.load(rf)
        self.start_block_number = block_data.get('{}_pledge'.format(self.chain))
        if self.start_block_number is None:
            self.start_block_number = app_config.CHAINS[self.chain]['FIRST_BLOCK']
        return block_data

    def __get_block_number(self):
        if not os.path.exists(self.block_number_file_path):
            block_data = self.use_yesterday_block_num()
        else:
            with open(self.block_number_file_path, 'r') as rf:
                data = rf.read().strip()
            if not data:
                block_data = self.use_yesterday_block_num()
            else:
                with open(self.block_number_file_path, 'r') as rf:
                    block_data = json.load(rf)
                if block_data.get('is_run'):
                    self.logger.info('get pledge data is running, wait.')
                    return False
                if block_data.get('block'):
                    self.start_block_number = block_data['block']
                else:
                    block_data = self.use_yesterday_block_num()
        with open(self.block_number_file_path, 'w') as wf:
            block_data['is_run'] = True
            json.dump(block_data, wf)
        return True

    def __set_block_number(self):
        block_data = {'block': self.end_block_number, 'is_run': False}
        with open(self.block_number_file_path, 'w') as wf:
            json.dump(block_data, wf)
        return True

    def __event_to_item(self, datas):
        for data in datas:
            event = '{}_{}'.format(data['event'], self.chain)
            block_number = data['blockNumber']
            stake_num = data['args']['_stakeNum']
            user_addr = data['args']['_userAddr'].lower()
            node_addr = data['args']['_nodeAddr'].lower()
            amount = data['args'].get('_amount', 0)
            _time = data['args'].get('_time')
            item = TbUserPledge(stake_num, event, block_number, user_addr, node_addr, amount, _time).to_dict()
            self.items.append(item)
        return self.items

    def __run_to_false(self):
        if not os.path.exists(self.block_number_file_path):
            return True
        with open(self.block_number_file_path, 'r+') as rf:
            block_data = json.load(rf)
            block_data['is_run'] = False
            rf.seek(0, 0)
            json.dump(block_data, rf)
        return True

    def get(self):
        try:
            self.__prepare_dir()
            if not self.__get_block_number():
                return False
            from_block = self.start_block_number + 1
            to_block = self.web3eth.get_last_block_number(self.pledge_address, PLEDGE_ABI) - 6
            self.end_block_number = to_block
            self.logger.info('from block: {}, to block: {}, interval: {}'.format(from_block, to_block, self.interval))
            if from_block > to_block:
                self.logger.info('from block > to block')
                self.__run_to_false()
                return True
            luca_count, wluca_count, end_luca_count, end_wluca_count = 0, 0, 0, 0
            for event_name in ['StakeLuca', 'EndStakeLuca', 'StakeWLuca', 'EndStakeWLuca']:
                for start_block in range(from_block, to_block + 1, self.interval):
                    end_block = start_block + self.interval - 1 if start_block + self.interval - 1 < to_block else to_block
                    while True:
                        try:
                            events = self.web3eth.get_pledge_events(event_name, start_block, end_block,
                                                                    address=self.pledge_address)
                            break
                        except Exception as e:
                            self.logger.error(
                                '{} from {} to {}, error:{}, try again'.format(event_name, start_block, end_block, e))
                            time.sleep(2)
                    self.logger.info('{} {} start block: {}, end block: {}, count: {}'
                                     .format(self.chain, event_name, start_block, end_block, len(events)))
                    if not events:
                        continue
                    if event_name in ['StakeLuca', 'StakeWLuca']:
                        if event_name == 'StakeLuca':
                            luca_count += len(events)
                        else:
                            wluca_count += len(events)
                        self.__event_to_item(events)
                    else:
                        self.__event_to_item(events)
                        if event_name == 'EndStakeLuca':
                            end_luca_count += len(events)
                        else:
                            end_wluca_count += len(events)
            self.logger.info('{} new pledge data num: luca: {}, wluca: {}, end_luca: {}, end_wluca: {}'
                             .format(self.chain, luca_count, wluca_count, end_luca_count, end_wluca_count))
            SaveData(self.web3eth, self.items, self.pledge_data_dir, self.chain, self.start_block_number,
                     self.end_block_number, self.block_interval, self.logger).save_to_file()
            self.__set_block_number()
            self.logger.info('this over.')
            return True
        except:
            self.logger.error(traceback.format_exc())
            if os.path.exists(self.block_number_file_path):
                self.__run_to_false()
            return False
