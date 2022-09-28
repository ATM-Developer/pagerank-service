from hashlib import md5

from project.jobs.base_import import *
from project.utils.coin_util import get_coin_price, luca_day_amount, day_amount


class FileJob():
    def __init__(self):
        self.data_dir = data_dir
        now_datetime = time_format(is_datetime=True)
        if now_datetime.hour >= app_config.OTHER_HOUR:
            self.today_date = time_format()[:10]
            self.yesterday_date = time_format(timedeltas={'days': 1}, opera=-1)[:10]
            self.tomorrow_date = time_format(timedeltas={'days': 1}, opera=1)[:10]
            self.cache_util = CacheUtil(date_type='time')
        else:
            self.today_date = time_format(timedeltas={'days': 1}, opera=-1)[:10]
            self.yesterday_date = time_format(timedeltas={'days': 2}, opera=-1)[:10]
            self.tomorrow_date = time_format()[:10]
            self.cache_util = CacheUtil()
        self.today_path = os.path.join(self.data_dir, self.today_date)
        self.today_executer_date = self.today_date + '_executer'
        self.today_executer_path = self.today_path + '_executer'
        self.today_total_earnings_path = os.path.join(self.today_path, CacheUtil._USER_TOTAL_EARNINGS_DIR)
        if not os.path.exists(self.data_dir):
            os.mkdir(self.data_dir)
        if not os.path.exists(self.today_path):
            os.mkdir(self.today_path)
        self.ipfs = IPFS(logger)
        self.web3eth = Web3Eth(logger)
        self.node_result = None
        self.is_download_yesterday = True
        self.coin_price_error_ratio = 0.03
        self.pagerank_datetime = '{} {}:{}:00'.format(self.today_date, app_config.START_HOUR, app_config.START_MINUTE)
        self.pagerank_timestamp = datetime_to_timestamp(self.pagerank_datetime)

    def get_yesterday_file_id(self):
        file_id = get_yesterday_file_id(self.web3eth,
                                        datetime_to_timestamp('{} {}:{}:00'.format(self.yesterday_date,
                                                                                   app_config.START_HOUR,
                                                                                   app_config.START_MINUTE)))
        logger.info('yesterday file id: {}'.format(file_id))
        return file_id

    def download_yesterday(self):
        if self.is_download_yesterday:
            logger.info('download yesterday data:')
            file_id = self.get_yesterday_file_id()
            file_name = '{}.tar.gz'.format(self.yesterday_date)
            logger.info('yesterday file id: {}, file name: {}'.format(file_id, file_name))
            if download_ipfs_file(self.ipfs, self.data_dir, file_id, file_name, logger, TarUtil):
                self.is_download_yesterday = False
            else:
                return False
        return True

    def prepare_datas(self):
        logger.info('prepare datas:')
        # if os.path.exists(os.path.join(self.today_path, CacheUtil._COIN_LIST_FILE_NAME)):
        #     os.remove(os.path.join(self.today_path, CacheUtil._COIN_LIST_FILE_NAME))
        # if os.path.exists(os.path.join(self.today_path, CacheUtil._LUCA_AMOUNT_FILE_NAME)):
        #     os.remove(os.path.join(self.today_path, CacheUtil._LUCA_AMOUNT_FILE_NAME))
        # if os.path.exists(os.path.join(self.today_path, CacheUtil._COIN_PRICE_FILE_NAME)):
        #     os.remove(os.path.join(self.today_path, CacheUtil._COIN_PRICE_FILE_NAME))
        # if os.path.exists(os.path.join(self.today_path, CacheUtil._COIN_PRICE_TEMP_FILE_NAME)):
        #     os.remove(os.path.join(self.today_path, CacheUtil._COIN_PRICE_TEMP_FILE_NAME))

        if not os.path.exists(os.path.join(self.today_path, CacheUtil._COIN_LIST_FILE_NAME)):
            coin_list = get_coin_list(logger, self.cache_util)
            self.cache_util.save_cache_coin_list(coin_list)
            logger.info('coin list datas ok.')

        if not os.path.exists(os.path.join(self.today_path, CacheUtil._COIN_PRICE_FILE_NAME)) and \
                not os.path.exists(os.path.join(self.today_path, CacheUtil._COIN_PRICE_TEMP_FILE_NAME)):
            coin_price = get_coin_price(logger, self.today_date, self.cache_util, self.web3eth)
            self.cache_util.save_cache_coin_price_temp(coin_price)
            logger.info('coin price datas ok.')

        if not os.path.exists(os.path.join(self.today_path, CacheUtil._LUCA_AMOUNT_FILE_NAME)):
            luca_amount = luca_day_amount(logger, self.cache_util)
            self.cache_util.save_cache_luca_amount(luca_amount)
            logger.info('luca amount datas ok.')

        if not os.path.exists(os.path.join(self.today_path, CacheUtil._DAY_AMOUNT_FILE_NAME)):
            day_amounts = day_amount(logger)
            self.cache_util.save_cache_day_amount(day_amounts)
            logger.info('day amount datas ok.')
        return True

    def repeat_prepare_data(self):
        if os.path.exists(os.path.join(self.today_path, CacheUtil._EARNINGS_TOP_NODES_DATAS_FILE_NAME)):
            os.remove(os.path.join(self.today_path, CacheUtil._EARNINGS_TOP_NODES_DATAS_FILE_NAME))
        top_nodes = self.web3eth.get_top_nodes()
        self.cache_util.save_top_nodes(top_nodes)
        logger.info('top servers data ok.')
        return True

    def tarfile_today(self):
        tar_file_name = os.path.join(self.data_dir, '{}.tar.gz'.format(self.today_date))
        TarUtil.tar_files(tar_file_name, tar_dir_list=[self.today_path])
        return tar_file_name

    def wait_data(self):
        logger.info('wait data...')
        need_files = [i for i in dir(CacheUtil) if i.isupper()]
        while True:
            is_continue = False
            for nf in need_files:
                if nf == '_PREFETCHING_EVENT_BLOCK_NUMBER_FILE_NAME' or nf == '_USER_TOTAL_EARNINGS_DIR' \
                        or nf == '_COIN_PRICE_TEMP_FILE_NAME':
                    continue
                if not os.path.exists(os.path.join(self.today_path, CacheUtil.__getattribute__(CacheUtil, nf))):
                    is_continue = True
                    break
            time.sleep(1)
            if not is_continue:
                break
        self.update_total_earnings()
        return True

    def upload_today(self):
        logger.info('today data ok, start upload.')
        tar_file_name = self.tarfile_today()
        return self.ipfs.upload(tar_file_name)

    def update_total_earnings(self):
        logger.info('update total earnings:')
        yesterday_total_earnings_path = os.path.join(self.data_dir, self.yesterday_date,
                                                     self.cache_util._USER_TOTAL_EARNINGS_DIR)
        if os.path.exists(self.today_total_earnings_path):
            shutil.rmtree(self.today_total_earnings_path)
        shutil.copytree(yesterday_total_earnings_path, self.today_total_earnings_path)
        # +
        self._update_total_earnings(CacheUtil._EARNINGS_TOP_NODES_DATAS_FILE_NAME, EarningsType.SERVER.value)
        self._update_total_earnings(CacheUtil._EARNINGS_PLEDGE_DATAS_FILE_NAME, EarningsType.PLEDGE.value)
        self._update_total_earnings(CacheUtil._EARNINGS_LIQUIDITY_DATAS_FILE_NAME, EarningsType.TRANSFER.value)
        self._update_total_earnings(CacheUtil._EARNINGS_MAIN_PR_DATAS_FILE_NAME, EarningsType.PR.value)
        self._update_total_earnings(CacheUtil._EARNINGS_NET_PR_DATAS_FILE_NAME, EarningsType.NET_PR.value)
        self._update_total_earnings(CacheUtil._EARNINGS_ALONE_PR_DATAS_FILE_NAME, EarningsType.ALONE_PR.value)
        # -
        self._reduction_total_earnings()

    def _update_total_earnings(self, file_name, e_type):
        logger.info('_update total earnings: {}'.format(e_type))
        file_path = os.path.join(self.today_path, file_name)
        with open(file_path) as rf:
            earnings_data = json.load(rf)
        for ed in earnings_data:
            user_address = ed['address']
            amount = Decimal(ed['amount'])
            coin_type = ed.get('coin', 'luca')
            addr_file = os.path.join(self.today_total_earnings_path, '{}.json'.format(user_address))
            now_timestamps = get_now_timestamp()
            coin_key = 'coin_{}'.format(coin_type)
            if os.path.exists(addr_file):
                with open(addr_file, 'r') as rf:
                    data = json.load(rf)
                new_amount = Decimal(data.get(coin_key, 0)) + amount
                data[coin_key] = str(new_amount)
                # if coin_type in data.keys():
                #     new_amount = Decimal(data[coin_type].get(e_type, 0)) + amount
                #     data[coin_type][e_type] = str(new_amount)
                # else:
                #     data[coin_type] = {}
                #     data[coin_type][e_type] = str(amount)
                data['update_timestamps'] = get_now_timestamp()
            else:
                data = {
                    'address': user_address,
                    'create_timestamps': now_timestamps,
                    'update_timestamps': now_timestamps,
                    coin_key: str(amount)
                }
            with open(addr_file, 'w') as wf:
                json.dump(data, wf)
        return True

    def _reduction_total_earnings(self):
        logger.info('reduction total earnings:')
        # data + block
        data_file = os.path.join(self.data_dir, 'prefetching_events', 'data_{}.txt'.format(self.today_date))
        datas = []
        with open(data_file, 'r') as rf:
            for item in rf.readlines():
                if item.strip():
                    datas.append(json.loads(item.strip()))
        haved = []
        for data in datas:
            user_address = data['address']
            nonce = data['nonce']
            if '{}_{}'.format(user_address, nonce) in haved:
                continue
            amount = Decimal(data['amount'])
            coin_type = data['coin_type']
            coin_key = 'coin_{}'.format(coin_type)
            addr_file = os.path.join(self.today_total_earnings_path, '{}.json'.format(user_address))
            with open(addr_file, 'r') as rf:
                addr_data = json.load(rf)
            new_amount = Decimal(addr_data.get(coin_key, 0)) - amount
            addr_data[coin_key] = str(new_amount)
            with open(addr_file, 'w') as wf:
                json.dump(addr_data, wf)
            haved.append('{}_{}'.format(user_address, nonce))
        with open(os.path.join(self.data_dir, 'prefetching_events', 'data_{}_end_block.txt'.format(self.today_date)),
                  'r') as rf:
            block_data = json.load(rf)
        self.cache_util.save_prefetching_block_number(block_data)
        return True

    def save_to_ipfs_contract(self):
        # get file id
        file_id = self.upload_today()
        logger.info('upload success: {}'.format(file_id))
        if not file_id:
            return False
        # push to snapshoot
        with open(os.path.join(self.data_dir, '{}.tar.gz'.format(self.today_date)), 'rb') as rbf:
            md5_hash = md5(rbf.read()).hexdigest()
        self.web3eth.send_snapshoot_proposal(md5_hash, file_id)
        logger.info('send proposal success.')
        return True

    def comparison_coin_price(self):
        if os.path.exists(os.path.join(self.today_path, CacheUtil._COIN_PRICE_FILE_NAME)):
            if os.path.exists(os.path.join(self.today_path, CacheUtil._COIN_PRICE_TEMP_FILE_NAME)):
                os.remove(os.path.join(self.today_path, CacheUtil._COIN_PRICE_TEMP_FILE_NAME))
            return True
        self_coin_price_temp = self.cache_util.get_today_coin_price_temp()
        logger.info('self coin price temp: {}'.format(self_coin_price_temp))
        with open(os.path.join(self.today_executer_path, CacheUtil._COIN_PRICE_FILE_NAME), 'r') as rf:
            executer_coin_price = json.load(rf)
        logger.info('executer coin price: {}'.format(executer_coin_price))
        if self_coin_price_temp.keys() != executer_coin_price.keys():
            logger.info('self_coin_price_temp.keys() != executer_coin_price.keys()')
            return False
        for sk, sv in self_coin_price_temp.items():
            ev = executer_coin_price[sk]
            lv = abs(sv - ev) / sv
            logger.info('coin: {}, self coin price: {} executer coin price: {}, lv: {}'.format(sk, sv, ev, lv))
            if lv > self.coin_price_error_ratio:
                return False
        self.cache_util.save_cache_coin_price(executer_coin_price)
        os.remove(os.path.join(self.today_path, CacheUtil._COIN_PRICE_TEMP_FILE_NAME))
        logger.info('comparison coin price ok.')
        return True

    def comparison_total_earnings_data(self, self_path, executer_path):
        self_path_listdir = os.listdir(self_path)
        executer_path_listdir = os.listdir(executer_path)
        # logger.info('{}, {}'.format(self_path_listdir, executer_path_listdir))
        if len(self_path_listdir) != len(executer_path_listdir):
            logger.info('self path listdir != executer path listdir')
            return False
        for f in os.listdir(self_path):
            self_earnings_path = os.path.join(self_path, f)
            executer_earnings_path = os.path.join(executer_path, f)
            if not os.path.exists(executer_earnings_path):
                logger.info('executer file not exists: {}'.format(f))
                return False
            with open(self_earnings_path, 'r') as rf:
                self_data = json.load(rf)
            with open(executer_earnings_path, 'r') as rf:
                executer_data = json.load(rf)
            if self_data.keys() != executer_data.keys():
                logger.info('self_data.keys != executer_data.keys, file: {}, self data: {}, executer data: {}'
                            .format(f, self_data, executer_data))
                return False
            for sk, sv in self_data.items():
                if sk in ['create_timestamps', 'update_timestamps']:
                    continue
                ev = executer_data[sk]
                if isinstance(sv, str) and sv != ev:
                    logger.info('self data != executer data, self data: {}, executer data: {}'
                                .format(self_data, executer_data))
                    return False
                elif isinstance(sv, dict):
                    if not isinstance(ev, dict):
                        logger.info('self data != executer data, self data: {}, executer data: {}'
                                    .format(self_data, executer_data))
                        return False
                    for xsk, xsv in sv.items():
                        esv = ev.get(xsk)
                        if xsv != esv:
                            logger.info('self data != executer data, self data: {}, executer data: {}'
                                        .format(self_data, executer_data))
                            return False
        return True

    def comparison_all_data(self):
        not_equal = []
        need_files = [i for i in dir(CacheUtil) if i.isupper()]
        for nf in need_files:
            if nf in ['_COIN_PRICE_TEMP_FILE_NAME']:
                continue
            self_path = os.path.join(self.today_path, CacheUtil.__getattribute__(CacheUtil, nf))
            executer_path = os.path.join(self.today_executer_path, CacheUtil.__getattribute__(CacheUtil, nf))
            if nf == '_USER_TOTAL_EARNINGS_DIR':
                if not self.comparison_total_earnings_data(self_path, executer_path):
                    return False
            else:
                if not os.path.exists(self_path) or not os.path.exists(executer_path):
                    not_equal.append(nf)
                with open(self_path, 'rb') as rbf:
                    self_hash = md5(rbf.read()).hexdigest()
                with open(executer_path, 'rb') as rbf:
                    executer_hash = md5(rbf.read()).hexdigest()
                if self_hash != executer_hash:
                    not_equal.append(nf)
        logger.info('not equal: {}'.format(not_equal))
        if not_equal and ['_BLOCK_NUMBER_FILE_NAME'] != not_equal:
            logger.info('not equal: {}'.format(not_equal))
            return False
        return True

    def senator_check_data(self, latest_proposal):
        logger.info('senator check data:')
        file_id = latest_proposal[3]
        file_name = '{}.tar.gz'.format(self.today_executer_date)
        download_ipfs_file(self.ipfs, self.data_dir, file_id, file_name, logger, TarUtil)
        # check the error of coin_price
        error_ratio = self.comparison_coin_price()
        if error_ratio:
            # small error or no error, use executer's coin_price
            self.wait_data()
            return self.comparison_all_data()
        else:
            # large error, reject the proposal
            return False

    def set_vote(self, check_result):
        if check_result:
            self.web3eth.set_vote(True)
            logger.info('set vote true.')
        else:
            self.web3eth.set_vote(False)
            logger.info('set vote false.')

    def senator_handler(self, start_timestamp):
        logger.info('senator wait set vote: ')
        start_time = time.time() if time.time() > self.pagerank_timestamp else self.pagerank_timestamp
        while True:
            try:
                latest_snapshoot_proposal = self.web3eth.get_latest_snapshoot_proposal()
                if start_timestamp < latest_snapshoot_proposal[5]:
                    break
                if latest_snapshoot_proposal[-1] == 0 and latest_snapshoot_proposal[5] > self.pagerank_timestamp:
                    break
                this_executer = self.web3eth.get_executer()
                if self.now_executer != this_executer:
                    logger.info('executer changed, old:{}, new:{}'.format(self.now_executer, this_executer))
                    self.now_executer = this_executer
                    return False
            except:
                pass
            if time.time() - start_time > app_config.ST_EPOCH * 60:
                logger.info('senator get latest proposal failed.')
                return False
            time.sleep(1)
        check_result = self.senator_check_data(latest_snapshoot_proposal)
        self.set_vote(check_result)
        return True

    def judge_node(self, start_timestamp):
        self.node_result = self.web3eth.is_senators_or_executer()
        logger.info('self address is : {}'.format(self.node_result))
        if not self.node_result:
            if self.web3eth.check_vote(self.today_date) == 1:
                return True
            else:
                time.sleep(5)
                return False
        return None

    def update_executer(self, start_timestamp):
        this_executer = self.web3eth.get_executer()
        if self.now_executer != this_executer:
            self.now_executer = this_executer
            return True
        if self.web3eth.is_violation(start_timestamp):
            logger.info('update executer not violation 1:')
            try:
                self.web3eth.update_executer()
                logger.info('update executer ok.')
                time.sleep(10)
            except:
                logger.info('update executer false.')
                time.sleep(10)
                this_executer = self.web3eth.get_executer()
                if self.now_executer == this_executer:
                    return False
        elif self.web3eth.is_violation2(self.now_executer, self.pagerank_timestamp):
            logger.info('update executer not violation 2:')
            result = self.web3eth.send_forced_change_executer_proposal()
            logger.info('send update executer proposal result : {}'.format(result))
            if result is False:
                return False
            if result == 'latest proposal has no resolution':
                self.web3eth.set_vote_update_executer_proposal(True)
            stimestamp = time.time()
            while True:
                this_executer = self.web3eth.get_executer()
                if this_executer != self.now_executer:
                    break
                if time.time() - stimestamp > app_config.VOTE_EPOCH * 60:
                    return False
                time.sleep(1)
        self.now_executer = this_executer if this_executer != self.now_executer else self.web3eth.get_executer()
        return True

    def to_handle_data(self, start_timestamp, times):
        if self.node_result == 'is executer':
            # if times > 1:
            latest_proposal = self.web3eth.get_latest_snapshoot_proposal()
            if latest_proposal[-1] == 0 and latest_proposal[-3] == app_config.WALLET_ADDRESS:
                return True
            if os.path.exists(os.path.join(self.today_path, CacheUtil._COIN_PRICE_TEMP_FILE_NAME)):
                shutil.move(os.path.join(self.today_path, CacheUtil._COIN_PRICE_TEMP_FILE_NAME),
                            os.path.join(self.today_path, CacheUtil._COIN_PRICE_FILE_NAME))
            self.wait_data()
            flag = self.save_to_ipfs_contract()
        else:
            flag = self.senator_handler(start_timestamp)
        return flag

    def delete_datas(self):
        f_list = os.listdir(self.today_path)
        if os.path.exists(os.path.join(os.path.join(self.today_path, CacheUtil._COIN_PRICE_FILE_NAME))):
            shutil.move(os.path.join(self.today_path, CacheUtil._COIN_PRICE_FILE_NAME),
                        os.path.join(self.today_path, CacheUtil._COIN_PRICE_TEMP_FILE_NAME))
        for f in f_list:
            if f in [CacheUtil._COIN_LIST_FILE_NAME, CacheUtil._LUCA_AMOUNT_FILE_NAME,
                     CacheUtil._COIN_PRICE_FILE_NAME, CacheUtil._COIN_PRICE_TEMP_FILE_NAME,
                     CacheUtil._DAY_AMOUNT_FILE_NAME]:
                continue
            del_path = os.path.join(self.today_path, f)
            if os.path.isfile(del_path):
                os.remove(del_path)
            else:
                shutil.rmtree(del_path)
        if os.path.exists(os.path.join(self.today_executer_path)):
            shutil.rmtree(os.path.join(self.today_executer_path))
            os.remove(os.path.join(self.today_executer_path + '.tar.gz'))
        return True

    def download_latest_snapshoot_ipfs_file(self):
        latest_success_snapshoot = self.web3eth.get_latest_snapshoot_proposal()
        file_id = latest_success_snapshoot[3]
        file_name = '{}.tar.gz'.format(self.today_date)
        download_ipfs_file(self.ipfs, self.data_dir, file_id, file_name, logger, TarUtil)
        return True

    def main(self):
        times = 1
        is_prepared = False
        start_timestamp = get_now_timestamp()
        self.now_executer = self.web3eth.get_executer()
        while True:
            try:
                logger.info('start data job: {}, {}'.format(times, start_timestamp))
                latest_success_snapshoot = self.web3eth.get_latest_snapshoot_proposal()
                if latest_success_snapshoot[-1] == 1 and latest_success_snapshoot[-2] > self.pagerank_timestamp:
                    logger.info('there are successful proposals today.')
                    self.download_latest_snapshoot_ipfs_file()
                    return True
                if not os.path.exists(self.today_path):
                    os.mkdir(self.today_path)
                if not self.download_yesterday():
                    times += 1
                    continue
                if not is_prepared and self.prepare_datas():
                    is_prepared = True
                self.repeat_prepare_data()
                judge_node_result = self.judge_node(start_timestamp)
                if judge_node_result:
                    self.download_latest_snapshoot_ipfs_file()
                    return True
                elif judge_node_result is False:
                    continue
                if not self.update_executer(start_timestamp):
                    time.sleep(2)
                    continue
                judge_node_result = self.judge_node(start_timestamp)
                if judge_node_result:
                    self.download_latest_snapshoot_ipfs_file()
                    return True
                elif judge_node_result is False:
                    continue
                if self.to_handle_data(start_timestamp, times) \
                        and check_vote(self.web3eth, logger, self.today_date, now_executer=self.now_executer):
                    logger.info('download snapshoot ifps file:')
                    self.download_latest_snapshoot_ipfs_file()
                    return True
                time.sleep(10)
                self.delete_datas()
                start_timestamp = get_now_timestamp()
                times += 1
            except:
                logger.error(traceback.format_exc())
                try:
                    if self.web3eth.check_vote(self.today_date) == 1:
                        logger.info('today proposal is success.')
                        self.download_latest_snapshoot_ipfs_file()
                        return True
                except:
                    pass
                # if os.path.exists(os.path.join(self.today_path, CacheUtil._COIN_PRICE_FILE_NAME)):
                #     shutil.move(os.path.join(self.today_path, CacheUtil._COIN_PRICE_FILE_NAME),
                #                 os.path.join(self.today_path, CacheUtil._COIN_PRICE_TEMP_FILE_NAME))
                if os.path.exists(os.path.join(self.today_path, CacheUtil._USER_TOTAL_EARNINGS_DIR)):
                    shutil.rmtree(os.path.join(self.today_path, CacheUtil._USER_TOTAL_EARNINGS_DIR))
                if os.path.exists(os.path.join(self.today_executer_path)):
                    shutil.rmtree(os.path.join(self.today_executer_path))
                    os.remove(os.path.join(self.today_executer_path + '.tar.gz'))
                time.sleep(5)
            times += 1


logger = logging.getLogger('data_job')


def do():
    FileJob().main()


def datajob():
    while True:
        try:
            hour = app_config.OTHER_HOUR
            minute = app_config.OTHER_MINUTE
            web3eth = Web3Eth(logger)
            latest_proposal = web3eth.get_latest_snapshoot_proposal()
            pagerank_data = get_pagerank_date()
            pagerank_timestamp = datetime_to_timestamp('{} {}:{}:00'.format(pagerank_data,
                                                                            app_config.START_HOUR,
                                                                            app_config.START_MINUTE))
            if latest_proposal[-1] == 1 and latest_proposal[5] > pagerank_timestamp:
                file_name = '{}.tar.gz'.format(pagerank_data)
                download_ipfs_file(IPFS(logger), data_dir, latest_proposal[3], file_name, logger, TarUtil)
                now_timestamp = get_now_timestamp()
                pagerank_date = get_pagerank_date(int(hour), int(minute))
                pagerank_datetime = '{} {}:{}:00'.format(pagerank_date, hour, minute)
                target_timestamp = datetime_to_timestamp(pagerank_datetime)
                next_datetime = timestamp_to_format2(target_timestamp, timedeltas={'days': 1}, opera=1)
                next_timestamp = datetime_to_timestamp(next_datetime)
                logger.info('now timestamp: {}, pagerank_datetime: {}, next datetime: {}, next timestamp: {}'
                            .format(now_timestamp, pagerank_datetime, next_datetime, next_timestamp))
                time_interval = next_timestamp - now_timestamp
                if time_interval < app_config.TIME_INTERVAL:
                    logger.info('< time interval, to run.')
                    if time_interval > 0:
                        time.sleep(next_timestamp - now_timestamp)
                        FileJob().main()
                    else:
                        FileJob().main()
            else:
                logger.info('the previous proposal failed. to run.')
                FileJob().main()
            scheduler.add_job(id='data_job2', func=do, trigger='cron', hour=int(hour), minute=int(minute))
            break
        except:
            logger.error(traceback.format_exc())


logger.info('IPFS data job Is Running:, pid:{}'.format(os.getpid()))
next_run_time = time_format(timedeltas={'seconds': 10}, opera=1, is_datetime=True)
scheduler.add_job(id='data_job', func=datajob, next_run_time=next_run_time)
