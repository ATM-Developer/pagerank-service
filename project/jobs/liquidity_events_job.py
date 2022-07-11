from project.configs.eth.eth_config import IERC20_ABI, DRAW_PRIVATE_ABI
from project.models.entity import TbTransferEvent
from project.jobs.base_import import *


class Handler():
    def __init__(self):
        self.items = []
        self.start_block_number = 0
        self.end_block_number = 0
        self.now_datetime = time_format()
        self.data_end_hour = app_config.DATA_END_HOUR
        self.data_end_minute = app_config.DATA_END_MINUTE
        self.web3eth = Web3Eth()
        self.contract_address = app_config.BUSD_LUCA_ADDRESS
        self.abi = IERC20_ABI
        self.other_hour = app_config.OTHER_HOUR
        self.other_minute = app_config.OTHER_MINUTE

    def __event_to_item(self, data):
        log_index = data['logIndex']
        from_addr = data['args'].get('from', '')
        from_addr = from_addr.lower()
        to_addr = data['args'].get('to', '')
        to_addr = to_addr.lower()
        value = data['args'].get('value', 0)
        event_time = data['timestamp']
        transaction_index = data['transactionIndex']
        transaction_hash = data['transactionHash'].hex()
        address = data['address']
        block_hash = data['blockHash'].hex()
        block_number = data['blockNumber']
        item = TbTransferEvent(log_index, from_addr, to_addr, value, event_time, transaction_index,
                               transaction_hash, address, block_hash, block_number).to_dict()
        item['_time'] = event_time
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
        self.liquidity_data_dir = os.path.join(self.data_dir, 'liquidity_data')
        self.today_date = self.now_datetime[:10]
        self.tomorrow_date = time_format(timedeltas={'days': 1}, opera=1)[:10]
        if not os.path.exists(self.liquidity_data_dir):
            os.makedirs(self.liquidity_data_dir)
        self.block_number_file_path = os.path.join(self.liquidity_data_dir, 'block_number.txt')
        self.tomorrow_data_file = os.path.join(self.liquidity_data_dir, 'data_{}.txt'.format(self.tomorrow_date))
        self.today_data_file = os.path.join(self.liquidity_data_dir, 'data_{}.txt'.format(self.today_date))
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
        pagerank_date = get_pagerank_date()
        yesterday_block_number_file_path = os.path.join(self.data_dir, pagerank_date,
                                                        CacheUtil._LIQUIDITY_BLOCK_NUMBER_FILE_NAME)
        if not os.path.exists(yesterday_block_number_file_path):
            # download ipfs yesterday data
            if not self.__download_yesterday(pagerank_date):
                logger.info('failed to download yesterday data.')
                return False
        with open(yesterday_block_number_file_path, 'r') as rf:
            block_data = json.load(rf)
        self.start_block_number = block_data.get('liquidity')
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
                    logger.info('get liquidity data is running, wait.')
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
            to_block = self.web3eth.get_last_block_number(self.contract_address, self.abi) - 6
            self.end_block_number = to_block
            logger.info('from block: {}, to block: {}'.format(from_block, to_block))
            if from_block > to_block:
                logger.info('from block > to block.')
                self.__run_to_false()
                return True
            event_count = 0
            interval = 5000
            for start_block in range(from_block, to_block + 1, interval):
                end_block = start_block + interval - 1 if start_block + interval - 1 < to_block else to_block
                while True:
                    try:
                        events = self.web3eth.get_transfer_events(start_block, end_block,
                                                                  self.contract_address, self.abi)
                        break
                    except Exception as e:
                        logger.info('from {} to {} error {}, try again'.format(start_block, end_block, e))
                event_count += len(events)
                logger.info('start block: {}, end block: {}, count: {}'.format(start_block, end_block, event_count))
                events = list(events)
                block_nums = [i.get('blockNumber') for i in events]
                block_nums = list(set(block_nums))
                block_num_infos = {}
                for block_num in block_nums:
                    block_info = self.web3eth.get_block_by_number(block_num)
                    block_num_infos[block_num] = block_info
                for event in events:
                    block_num = event['blockNumber']
                    info = block_num_infos[block_num]
                    event = dict(event)
                    event['timestamp'] = info.get('timestamp')
                    self.__event_to_item(event)
            # self.__get_block_number_info()
            logger.info('block over.')
            SaveData(self.web3eth, self.items, self.liquidity_data_dir, 'data', self.start_block_number,
                     self.end_block_number).save_to_file()
            self.__set_block_number()
            logger.info('this over.')
            return True
        except:
            logger.error(traceback.format_exc())
            if os.path.exists(self.block_number_file_path):
                self.__run_to_false()
            return False


logger = logging.getLogger('liquidity_data')


def get_liquidity_data():
    try:
        handler = Handler()
        handler.get()
    except:
        logger.error(traceback.format_exc())


logger.info('get liquidity data Job Is Running, pid:{}'.format(os.getpid()))
block_number_path = os.path.join(data_dir, 'liquidity_data', 'block_number.txt')
reset_block_number_file(block_number_path)
scheduler.add_job(id='liquidity_data', func=get_liquidity_data, trigger='cron', minute="*/2")
