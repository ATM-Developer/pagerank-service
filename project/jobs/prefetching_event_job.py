from project.configs.eth.eth_config import INCENTIVE_ABI
from project.jobs.base_import import *
from project.utils.withdraw_event_util import append_to_day_files, event_key, item_key, recorded_keys, \
    withdraw_events_lock, write_temp_file

# Some public RPCs (seen with bsc.api.pocket.network) report a block_number
# ahead of what their log index has, so a getLogs call near the chain tip can
# silently return only part of the WithdrawToken events with no error. The
# cursor then moves past them and the withdrawal is never deducted on that node.
# Every run re-queries this many blocks behind the cursor (~15 min at ~0.45s
# per block) and records only events not already in the day files, so a
# partial answer from one run is filled in by a later one.
RESCAN_BLOCKS = 2000


class PrefetchingEvents():
    def __init__(self):
        self.items = []
        self.start_block_number = 0
        self.end_block_number = 0
        # lowest block a rescan may reach; set when the cursor is bootstrapped
        # from yesterday's IPFS data so a rescan never pulls in events from a
        # day this node has no local data file for.
        self.floor_block_number = 0
        self.now_datetime = time_format()
        self.web3eth = Web3Eth(logger)
        self.data_end_hour = app_config.DATA_END_HOUR
        self.data_end_minute = app_config.DATA_END_MINUTE

    def judge_coin_type(self, coin_address, coin_data):
        coin_type = ''
        for coin_info in coin_data.get('coinCurrencyPairList', {}).get('pre', []):
            if coin_address == coin_info['gateWay']:
                coin_type = coin_info['baseCurrency'].lower()
                break
        return coin_type

    def __event_to_item(self, event, coin_data):
        _amount = event['args']['_amount']
        amount = Web3.fromWei(_amount, 'ether')
        hash_value = event['transactionHash'].hex()
        coin_address = '0x51E6Ac1533032E72e92094867fD5921e3ea1bfa0' # self.web3eth.get_transaction_coin_address(hash_value)
        coin_type = 'luca' # self.judge_coin_type(coin_address, coin_data)
        item = {
            'address': event['args']['_userAddr'].lower(),
            'nonce': event['args']['_nonce'],
            'amount': str(amount),
            'hash_value': hash_value,
            'block_number': event['blockNumber'],
            'coin_address': coin_address,
            'coin_type': coin_type
        }
        self.items.append(item)

    def __get_block_number_info(self):
        block_nums = [i.get('block_number') for i in self.items]
        block_nums = list(set(block_nums))
        block_num_infos = {}
        for block_num in block_nums:
            block_info = self.web3eth.get_block_by_number(block_num)
            block_num_infos[block_num] = block_info
        for i in self.items:
            block_num = i['block_number']
            i['_time'] = block_num_infos[block_num]['timestamp']
        return True

    def __prepare_dir(self):
        self.data_dir = data_dir
        self.p_event_data_dir = os.path.join(self.data_dir, 'prefetching_events')
        self.today_date = self.now_datetime[:10]
        self.tomorrow_date = time_format(timedeltas={'days': 1}, opera=1)[:10]
        if not os.path.exists(self.p_event_data_dir):
            os.makedirs(self.p_event_data_dir)
        self.block_number_file_path = os.path.join(self.p_event_data_dir, 'block_number.txt')
        self.tomorrow_data_file = os.path.join(self.p_event_data_dir, 'data_{}.txt'.format(self.tomorrow_date))
        self.today_data_file = os.path.join(self.p_event_data_dir, 'data_{}.txt'.format(self.today_date))
        self.temp_dir = os.path.join(self.p_event_data_dir, 'temp_file')
        if not os.path.exists(self.temp_dir):
            os.mkdir(self.temp_dir)
        return True

    def __download_yesterday(self, pagerank_date):
        logger.info('download yesterday data:')
        with open(self.block_number_file_path, 'w') as wf:
            json.dump({"is_run": True}, wf)
        file_id = get_yesterday_file_id(self.web3eth,
                                        datetime_to_timestamp('{} {}:{}:00'.format(pagerank_date, app_config.START_HOUR,
                                                                                   app_config.START_MINUTE)))
        file_name = '{}.tar.gz'.format(pagerank_date)
        ipfs = IPFS(logger)
        return download_ipfs_file(ipfs, self.data_dir, file_id, file_name, logger, TarUtil)

    def use_yesterday_block_num(self):
        # use ipfs block_num
        pagerank_date = time_format(timedeltas={'days': 1}, opera=-1)[:10]
        yesterday_block_number_file_path = os.path.join(self.data_dir, pagerank_date,
                                                        CacheUtil._PREFETCHING_EVENT_BLOCK_NUMBER_FILE_NAME)
        if not os.path.exists(yesterday_block_number_file_path):
            # download ipfs yesterday data
            if not self.__download_yesterday(pagerank_date):
                logger.info('failed to download yesterday data.')
                return False
        with open(yesterday_block_number_file_path, 'r') as rf:
            block_data = json.load(rf)
        self.start_block_number = block_data.get('block')
        if self.start_block_number is None:
            self.start_block_number = app_config.CHAINS['binance']['FIRST_BLOCK']
        self.floor_block_number = self.start_block_number
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
                    logger.info('get prefetching events is running, wait.')
                    return False
                if block_data.get('block'):
                    self.start_block_number = block_data['block']
                    self.floor_block_number = block_data.get('floor', self.start_block_number)
                else:
                    block_data = self.use_yesterday_block_num()
        with open(self.block_number_file_path, 'w') as wf:
            block_data['is_run'] = True
            json.dump(block_data, wf)
        return True

    def __set_block_number(self):
        block_data = {'block': self.end_block_number, 'floor': self.floor_block_number, 'is_run': False}
        with open(self.block_number_file_path, 'w') as wf:
            json.dump(block_data, wf)
        return True

    def __recorded_keys(self):
        # A rescan window only reaches ~15 min back, so its events can only
        # belong to yesterday, today or tomorrow's day file.
        keys = set()
        yesterday_date = time_format(timedeltas={'days': 1}, opera=-1)[:10]
        for date in (yesterday_date, self.today_date, self.tomorrow_date):
            keys |= recorded_keys(os.path.join(self.p_event_data_dir, 'data_{}.txt'.format(date)))
        return keys

    def __save_to_temp_dir(self):
        # written whole, so prefetching_chain_job never reads a half-written file
        for data in self.items:
            write_temp_file(self.p_event_data_dir, data)

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
            to_block = self.web3eth.get_last_block_number(app_config.INCENTIVE_ADDRESS, INCENTIVE_ABI) - 36
            if self.start_block_number + 1 > to_block:
                logger.info('from block > to block.')
                self.__run_to_false()
                return True
            from_block = max(self.start_block_number + 1 - RESCAN_BLOCKS, self.floor_block_number + 1)
            self.end_block_number = to_block
            logger.info('from block: {} (cursor {}), to block: {}'.format(from_block, self.start_block_number, to_block))
            recorded = self.__recorded_keys()
            interval = 5000
            coin_data = None
            for start_block in range(from_block, to_block + 1, interval):
                end_block = start_block + interval - 1 if start_block + interval - 1 < to_block else to_block
                while True:
                    try:
                        events = self.web3eth.get_incentive_events(start_block, end_block)
                        break
                    except Exception as e:
                        logger.info('from {} to {} error: {}, rpc: {}, try again'.format(
                            start_block, end_block, self.web3eth.describe_error(e), self.web3eth.rpc_name()))
                        time.sleep(2)
                logger.info('start block: {}, end block: {}, incentive count: {}, rpc: {}{}'.format(
                    start_block, end_block, len(events), self.web3eth.rpc_name(),
                    ', events: {}'.format(self.web3eth.event_refs(events)) if events else ''))
                if events and coin_data is None:
                    coin_data = get_coin_list(logger)
                for event in events:
                    key = event_key(event)
                    if key in recorded:
                        continue
                    if event['blockNumber'] <= self.start_block_number:
                        logger.info('rescan recovered missed event: {}'.format(str(event)))
                    else:
                        logger.info('this event: {}'.format(str(event)))
                    recorded.add(key)
                    self.__event_to_item(event, coin_data)
            self.__get_block_number_info()
            logger.info('block over.')
            # The lock is held for file I/O only. SaveData's day-boundary
            # bookkeeping looks blocks up over RPC (retries on a bad RPC, and an
            # end-block search once a day), so it runs after the lock is
            # released, with the items already written - it files items by the
            # same rule append_to_day_files uses.
            with withdraw_events_lock(self.p_event_data_dir):
                # withdraw_check_job may have recorded some of these while this run was querying
                recorded = self.__recorded_keys()
                self.items = [i for i in self.items if item_key(i) not in recorded]
                append_to_day_files(self.p_event_data_dir, self.items, logger)
                self.__save_to_temp_dir()
            SaveData(self.web3eth, [], self.p_event_data_dir, 'data', self.start_block_number,
                     self.end_block_number, 19.95, logger).save_to_file()
            self.__set_block_number()
            logger.info('this over.')
            return True
        except:
            logger.error(traceback.format_exc())
            if os.path.exists(self.block_number_file_path):
                self.__run_to_false()
            return False


logger = logging.getLogger('prefetching_events')


def prefetching_events():
    try:
        PrefetchingEvents().get()
    except:
        logger.error(traceback.format_exc())


logger.info('get prefetching events Job Is Running, pid:{}'.format(os.getpid()))
block_number_path = os.path.join(data_dir, 'prefetching_events', 'block_number.txt')
reset_block_number_file(block_number_path)
scheduler.add_job(id='prefetching_events', func=prefetching_events, trigger='cron', minute="*/2")
