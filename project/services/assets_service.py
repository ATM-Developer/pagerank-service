import os
import json
from decimal import Decimal, getcontext
getcontext().prec = 100

from project.extensions import logger, app_config
from project.utils.date_util import get_now_timestamp, timestamp_to_format2, get_pagerank_date, datetime_to_timestamp
from project.utils.settings_util import get_cfg
from project.utils.cache_util import CacheUtil

# from project.utils.tar_util import TarUtil
# from project.utils.helper_util import download_ipfs_file
# from project.services.ipfs_service import IPFS

data_dir = get_cfg('setting', 'data_dir', path_join=True)


class Assets():
    def __init__(self, user_address, web3eth, coin_type='luca'):
        self.user_address = user_address.lower()
        self.coin_type = coin_type
        self.web3eth = web3eth
        self.proposal_time = None
        self.proposal_datetime = None
        self.proposal_date = None
        self.data_dir = data_dir

    def __get_latest_snapshoot(self):
        pagerank_date = get_pagerank_date()
        while True:
            proposal = self.web3eth.get_latest_success_snapshoot_proposal()
            if proposal[-2] < datetime_to_timestamp('{} {}:{}:00'.format(pagerank_date, app_config.START_HOUR,
                                                                         app_config.START_MINUTE)):
                return None
            else:
                return proposal

    def __get_total(self):
        # get latest snapshoot
        latest_effective_snapshoot = self.__get_latest_snapshoot()
        if latest_effective_snapshoot is None:
            logger.info('get user assets not get latest effective snapshoot.')
            return {}
        self.proposal_time = latest_effective_snapshoot[5]
        self.proposal_datetime = timestamp_to_format2(self.proposal_time)
        logger.info('addr: {}, latest proposal: {}, datetime: {}'.format(self.user_address, latest_effective_snapshoot,
                                                                         self.proposal_datetime))
        # check proposal time
        if self.proposal_datetime > "{} {}:{}:00".format(self.proposal_datetime[:10], app_config.START_HOUR,
                                                         app_config.START_MINUTE):
            self.proposal_date = self.proposal_datetime[:10]
        else:
            self.proposal_date = timestamp_to_format2(self.proposal_time, timedeltas={'days': 1}, opera=-1)[:10]
        # get snapshoot files from IPFS
        if not os.path.exists(os.path.join(self.data_dir, self.proposal_date + ".tar.gz")):
            # file_id = latest_effective_snapshoot[3]
            # file_name = '{}.tar.gz'.format(self.proposal_date)
            # ipfs = IPFS(logger)
            # download_ipfs_file(ipfs, self.data_dir, file_id, file_name, logger, TarUtil)
            logger.info('no latest snapshoot file, wait')
            return {}
        if not os.path.exists(os.path.join(self.data_dir, self.proposal_date)):
            logger.info('get user assets download ipfs file failed.')
            return {}
        user_path = os.path.join(self.data_dir, self.proposal_date, CacheUtil._USER_TOTAL_EARNINGS_DIR,
                                 '{}.json'.format(self.user_address))
        if not os.path.exists(user_path):
            return {}
        with open(user_path) as rf:
            user_data = json.load(rf)
        # assets = {}
        # for k, v in user_data.items():
        #     if isinstance(v, dict):
        #         total = 0
        #         for amount in v.values():
        #             total += Decimal(str(amount))
        #         assets[k] = total
        return user_data  # assets

    def __get_prefetching(self):
        events = []
        prefetching_data_dir = os.path.join(self.data_dir, 'prefetching_events')
        for f in os.listdir(prefetching_data_dir):
            f_path = os.path.join(prefetching_data_dir, f)
            if os.path.isdir(f_path):
                continue
            if f > 'data_{}.txt'.format(self.proposal_date):
                with open(f_path, 'r') as rf:
                    for data in rf.readlines():
                        if data.strip():
                            data = json.loads(data)
                            address = data.get('address')
                            if len(data.keys()) > 1 and address == self.user_address:
                                events.append(data)
        return events

    def get(self):
        # get assets info
        total_assets = self.__get_total()
        logger.info('user_address: {}, total assets: {}'.format(self.user_address, total_assets))
        assets = Decimal(str(total_assets.get('coin_{}'.format(self.coin_type), 0)))
        if not assets:
            return {self.coin_type: {"total": assets}}
        # get all prefetching success events from 22 o'clock
        events = self.__get_prefetching()
        # calculate current assets: total - prefetchings
        for event in events:
            amount = Decimal(event['amount'])
            assets -= amount

        return {self.coin_type: {'total': assets}}


def check_prefetching_interval(user_address, coin_type):
    interval_dir = os.path.join(data_dir, 'prefetching', 'interval')
    user_file = os.path.join(interval_dir, '{}_{}.json'.format(user_address, coin_type))
    if not os.path.exists(user_file):
        return True
    with open(user_file, 'r') as rf:
        interval_data = json.load(rf)
    now_timestamp = get_now_timestamp()
    logger.info('user_addr: {}, coin_type: {}, now timestamps: {}, interval data: {}'
                .format(user_address, coin_type, now_timestamp, interval_data))
    logger.info('now timestamp: {}, last timestamp: {}'.format(now_timestamp, interval_data['expected_expiration']))
    if now_timestamp > interval_data['expected_expiration'] + 600:
        return True
    return False


def save_prefetching_interval(user_addr, coin_type, expected_expiration):
    interval_dir = os.path.join(data_dir, 'prefetching', 'interval')
    if not os.path.exists(interval_dir):
        try:
            os.makedirs(interval_dir)
        except:
            pass
    user_file = os.path.join(interval_dir, '{}_{}.json'.format(user_addr, coin_type))
    interval_data = {'prefetching_timestamps': get_now_timestamp(), 'expected_expiration': expected_expiration}
    with open(user_file, 'w') as wf:
        json.dump(interval_data, wf)
    return True
