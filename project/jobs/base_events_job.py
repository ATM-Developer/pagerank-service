# -*- encoding: utf-8 -*-

from project.jobs.base_import import *
from project.utils.settings_util import BASE_DIR


class BaseEventsHandler():
    web3eth_class = Web3Eth

    def __init__(self, event_name, logger):
        self.items = []
        self.start_block_number = 0
        self.end_block_number = 0
        self.now_datetime = time_format()
        self.data_end_hour = app_config.DATA_END_HOUR
        self.data_end_minute = app_config.DATA_END_MINUTE
        self.other_hour = app_config.OTHER_HOUR
        self.other_minute = app_config.OTHER_MINUTE
        self.data_dir = data_dir
        self.event_name = event_name
        self.logger = logger
        self.web3eth = None

        self.contract_address = app_config.EVENTS[self.event_name]['ADDRESS']
        abi_path = os.path.join(BASE_DIR, 'project/configs/eth', app_config.EVENTS[self.event_name]['ABI'])
        with open(abi_path) as rf:
            self.abi = json.load(rf)
        self.chain = app_config.EVENTS[self.event_name]['CHAIN']
        self.interval = app_config.CHAINS[self.chain]['INTERVAL']
        self.block_interval = app_config.CHAINS[self.chain]['BLOCK_INTERVAL']
        self.launch_date = app_config.EVENTS[self.event_name]['LAUNCH_DATE']

    def event_to_item(self, data):
        pass

    def archive_cursor_file(self):
        return '{}_block_number.txt'.format(self.event_name)

    def archive_cursor_block(self, block_data):
        return block_data.get('block')

    def __prepare_dir(self):
        self.event_data_dir = os.path.join(self.data_dir, self.event_name)
        self.today_date = self.now_datetime[:10]
        self.tomorrow_date = time_format(timedeltas={'days': 1}, opera=1)[:10]
        if not os.path.exists(self.event_data_dir):
            os.makedirs(self.event_data_dir)
        self.block_number_file_path = os.path.join(self.event_data_dir, 'block_number.txt')
        self.tomorrow_data_file = os.path.join(self.event_data_dir, 'data_{}.txt'.format(self.tomorrow_date))
        self.today_data_file = os.path.join(self.event_data_dir, 'data_{}.txt'.format(self.today_date))
        return True

    def __download_yesterday(self, pagerank_date):
        self.logger.info('download yesterday data:')
        with open(self.block_number_file_path, 'w') as wf:
            json.dump({"is_run": True}, wf)
        file_id = get_yesterday_file_id(self.web3eth_class(self.logger),
                                        datetime_to_timestamp('{} {}:{}:00'.format(pagerank_date, app_config.START_HOUR,
                                                                                   app_config.START_MINUTE)))
        file_name = '{}.tar.gz'.format(pagerank_date)
        ipfs = IPFS(self.logger)
        return download_ipfs_file(ipfs, self.data_dir, file_id, file_name, self.logger, TarUtil)

    def use_yesterday_block_num(self):
        pagerank_date = get_pagerank_date()
        yesterday_block_number_file_path = os.path.join(self.data_dir, pagerank_date, self.archive_cursor_file())
        if not os.path.exists(yesterday_block_number_file_path):
            if not self.__download_yesterday(pagerank_date):
                self.logger.info('failed to download yesterday data.')
                return False
        if not os.path.exists(yesterday_block_number_file_path):
            block_data = {}
        else:
            with open(yesterday_block_number_file_path, 'r') as rf:
                block_data = json.load(rf)
        self.start_block_number = self.archive_cursor_block(block_data)
        if self.start_block_number is None:
            self.start_block_number = app_config.EVENTS[self.event_name]['FIRST_BLOCK']
        self.logger.info('cold start: resuming from block {} ({})'.format(
            self.start_block_number, 'archive' if self.archive_cursor_block(block_data) is not None else 'FIRST_BLOCK'))
        return {'block': self.start_block_number}

    def __read_block_data(self):
        if not os.path.exists(self.block_number_file_path):
            return {}
        try:
            with open(self.block_number_file_path, 'r') as rf:
                data = rf.read().strip()
            return json.loads(data) if data else {}
        except (OSError, ValueError):
            self.logger.error('unreadable {}, treating as no cursor: {}'.format(
                self.block_number_file_path, traceback.format_exc()))
            return {}

    def __write_block_data(self, block_data):
        with open(self.block_number_file_path, 'w') as wf:
            json.dump(block_data, wf)

    def __get_block_number(self):
        block_data = self.__read_block_data()
        if block_data.get('is_run'):
            self.logger.info('get {} is running, wait.'.format(self.event_name))
            return False
        if block_data.get('block'):
            self.start_block_number = block_data['block']
        else:
            block_data = self.use_yesterday_block_num()
            if block_data is False:
                self.__run_to_false()
                return False
        block_data['is_run'] = True
        self.__write_block_data(block_data)
        return True

    def __set_block_number(self):
        block_data = {'block': self.end_block_number, 'is_run': False}
        self.logger.info('save path: {}, info: {}'.format(self.block_number_file_path, block_data))
        self.__write_block_data(block_data)
        return True

    def __run_to_false(self):
        if not os.path.exists(self.block_number_file_path):
            return True
        block_data = self.__read_block_data()
        block_data['is_run'] = False
        self.__write_block_data(block_data)
        return True

    def get_events_datas(self, start_block, end_block, retry_times):
        pass

    def get(self):
        try:
            self.__prepare_dir()
            if not self.__get_block_number():
                return False
            from_block = self.start_block_number + 1
            self.web3eth = self.web3eth_class(self.logger, self.chain)
            to_block = self.web3eth.get_last_block_number(self.contract_address, self.abi) - 36
            self.end_block_number = to_block
            self.logger.info('from block: {}, to block: {}, pending blocks: {}'.format(
                from_block, to_block, to_block - from_block + 1))
            if from_block > to_block:
                self.logger.info('from block > to block.')
                self.__run_to_false()
                return True
            event_count = 0
            retry_times = 10
            if 'DOMAIN' in app_config.__dict__ and app_config.DOMAIN == 'dev':
                retry_times = 1
            for start_block in range(from_block, to_block + 1, self.interval):
                end_block = start_block + self.interval - 1 if start_block + self.interval - 1 < to_block else to_block
                fetch_failed = False
                while True:
                    try:
                        events = self.get_events_datas(start_block, end_block, retry_times)
                        break
                    except Exception as e:
                        if 'DOMAIN' in app_config.__dict__ and app_config.DOMAIN == 'dev':
                            fetch_failed = True
                            fetch_error = e
                            break
                        self.logger.info('from {} to {} error: {}, rpc: {}, try again'.format(
                            start_block, end_block, self.web3eth.describe_error(e), self.web3eth.rpc_name()))
                        time.sleep(2)
                if fetch_failed:
                    self.end_block_number = start_block - 1
                    self.logger.info('from {} to {} fetch failed - stopping this run, next run resumes from {}. error: {}, rpc: {}'.format(
                        start_block, end_block, start_block, self.web3eth.describe_error(fetch_error), self.web3eth.rpc_name()))
                    break
                event_count += len(events)
                events = list(events)
                self.logger.info(
                    'start block: {}, end block: {}, records added: {}, total records so far: {}, '
                    'blocks remaining: {}, rpc: {}{}'.format(
                        start_block, end_block, len(events), event_count, to_block - end_block,
                        self.web3eth.rpc_name(),
                        ', events: {}'.format(self.web3eth.event_refs(events)) if events else ''))
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
                    self.event_to_item(event)
            self.logger.info('block over. total blocks processed: {}, total records collected: {}'.format(
                to_block - from_block + 1, len(self.items)))
            SaveData(self.web3eth, self.items, self.event_data_dir, 'data', self.start_block_number,
                     self.end_block_number, self.block_interval, self.logger).save_to_file(self.launch_date)
            self.__set_block_number()
            self.logger.info('this over.')
            return True
        except:
            self.logger.error(traceback.format_exc())
            if os.path.exists(self.block_number_file_path):
                self.__run_to_false()
            return False
