from project.configs.eth.eth_config import INCENTIVE_ABI
from project.jobs.base_import import *


class PrefetchingEvents():
    def __init__(self):
        self.items = []
        self.start_block_number = 0
        self.end_block_number = 0
        self.now_datetime = time_format()
        self.web3eth = Web3Eth()
        self.data_end_hour = app_config.DATA_END_HOUR
        self.data_end_minute = app_config.DATA_END_MINUTE

    def judge_coin_type(self, coin_address, coin_data):
        coin_type = ''
        for coin_info in coin_data.get('coinCurrencyPairList', []):
            if coin_address == coin_info['gateWay']:
                coin_type = coin_info['baseCurrency'].lower()
                break
        return coin_type

    def __event_to_item(self, event, coin_data):
        _amount = event['args']['_amount']
        amount = Web3.fromWei(_amount, 'ether')
        hash_value = event['transactionHash'].hex()
        coin_address = self.web3eth.get_transaction_coin_address(hash_value)
        coin_type = self.judge_coin_type(coin_address, coin_data)
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
        file_id = get_yesterday_file_id(datetime_to_timestamp('{} {}:{}:00'.format(pagerank_date, app_config.START_HOUR,
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

    def __save_to_temp_dir(self):
        for data in self.items:
            address = data['address']
            nonce = data['nonce']
            temp_file_path = os.path.join(self.temp_dir, '{}_{}.txt'.format(address, nonce))
            with open(temp_file_path, 'w') as wf:
                json.dump(data, wf)

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
            to_block = self.web3eth.get_last_block_number(app_config.INCENTIVE_ADDRESS, INCENTIVE_ABI) - 6
            self.end_block_number = to_block
            logger.info('from block: {}, to block: {}'.format(from_block, to_block))
            if from_block > to_block:
                logger.info('from block > to block.')
                self.__run_to_false()
                return True
            interval = 5000
            coin_data = None
            for start_block in range(from_block, to_block + 1, interval):
                end_block = start_block + interval - 1 if start_block + interval - 1 < to_block else to_block
                while True:
                    try:
                        events = self.web3eth.get_incentive_events(start_block, end_block)
                        break
                    except Exception as e:
                        logger.info('from {} to {} error {}, try again'.format(start_block, end_block, e))
                logger.info('from : {} to : {}, incentive count:{}'.format(from_block, to_block, len(events)))
                if events and coin_data is None:
                    coin_data = get_coin_list(logger)
                for event in events:
                    logger.info('this event: {}'.format(str(event)))
                    self.__event_to_item(event, coin_data)
            self.__get_block_number_info()
            logger.info('block over.')
            SaveData(self.web3eth, self.items, self.p_event_data_dir, 'data', self.start_block_number,
                     self.end_block_number).save_to_file()
            self.__save_to_temp_dir()
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


try:
    logger.info('get prefetching events Job Is Running')
    block_number_path = os.path.join(data_dir, 'prefetching_events', 'block_number.txt')
    reset_block_number_file(block_number_path)
    f = open(os.path.join(lock_file_dir_path, 'prefetching_events.txt'), 'w')
    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    f.write(str(time.time()))
    scheduler.add_job(id='prefetching_events', func=prefetching_events, trigger='cron', minute="*/2")
    time.sleep(3)
    fcntl.flock(f, fcntl.LOCK_UN)
    f.close()
except:
    try:
        f.close()
    except:
        pass
    logger.error(traceback.format_exc())
