from project.jobs.base_import import *


class TransferEarnings():
    def __init__(self):
        self.web3eth = Web3Eth(logger)
        self.cache_util = CacheUtil()
        self.zero_addr = '0x0000000000000000000000000000000000000000'
        self.data_file_path = data_dir
        self.a_address = app_config.A_ADDRESS.lower()
        self.invest_address = app_config.INVEST_ADDRESS.lower()

    def init(self):
        self.users_transfer = {}
        self.old_trans = []
        self.new_trans = []
        self.private_placement_datas = []
        self.percentage_datas = {}
        self.percentage_addresses = {}
        self.end_block_number = 0
        self.total_value = 0
        self.earnings_datas = []
        self.liquidity_reward = 0

    def get_datas_from_ipfs(self):
        self.old_trans = self.cache_util.get_cache_liquidity_datas()
        return True

    def get_private_liquidity(self):
        self.private_placement_datas = self.cache_util.get_cache_private_placementliquidity_datas()
        for k, v in self.private_placement_datas.items():
            self.trans(k, Decimal(str(v)), 1)
        self.users_transfer[self.invest_address] = 0

    def get_percentage_datas_from_ipfs(self):
        # {"user_address: [{"to_address": "xxx", "percentage": 0.12341}]}
        self.percentage_datas = self.cache_util.get_cache_liquidity_percentages()
        self.percentage_addresses = {}
        for k, v in self.percentage_datas.items():
            self.percentage_addresses[k] = [i['to_address'] for i in v]
        return True

    def get_new_liquidity_datas(self):
        new_data_file_path = os.path.join(self.data_file_path, 'liquidity_data',
                                          'data_{}.txt'.format(get_pagerank_date()))
        with open(new_data_file_path, 'r') as rf:
            for item in rf.readlines():
                if item.strip():
                    item = sorted(json.loads(item.strip()).items(), key=lambda k: k[0])
                    if item not in self.new_trans:
                        self.new_trans.append(item)
        new_blockbu_file_path = os.path.join(self.data_file_path, 'liquidity_data',
                                             'data_{}_end_block.txt'.format(get_pagerank_date()))
        with open(new_blockbu_file_path, 'r') as rf:
            block_data = json.load(rf)
        self.end_block_number = block_data['block']
        self.new_trans = [dict(i) for i in self.new_trans]
        self.new_trans = sorted(self.new_trans, key=lambda x: x['date_time'])
        return True

    def save_today_datas(self):
        self.old_trans = [dict(i) for i in self.old_trans if isinstance(i, list)]  # todo 下一次更新删除
        self.cache_util.save_liquidity_datas(self.old_trans + self.new_trans)
        self.cache_util.save_liquidity_block_number({"liquidity": self.end_block_number})
        self.cache_util.save_liquidity_percentages(self.percentage_datas)
        self.cache_util.save_earnings_liquidity(self.earnings_datas)
        self.cache_util.save_private_placement_liquidity_datas(self.private_placement_datas)
        return True

    def trans(self, addr, value, stype):
        """
        :param stype: 1: +; -1: -
        """
        value = Decimal(str(value)) * stype
        try:
            self.users_transfer[addr] += value
        except:
            self.users_transfer[addr] = value

    def statistic_user_trans(self, trans_datas):
        for item in trans_datas:
            item = dict(item)
            from_addr = item['from_addr']
            to_addr = item['to_addr']
            value = item['value']
            if from_addr == self.zero_addr and to_addr == self.a_address:
                continue
            if from_addr == self.zero_addr and to_addr == self.invest_address:
                continue
            if from_addr == self.a_address and to_addr == self.invest_address:
                continue
            if from_addr == self.invest_address:
                if to_addr in self.percentage_addresses[from_addr]:
                    self.trans(to_addr, value, -1)
                    continue
            if from_addr != self.zero_addr:
                self.trans(from_addr, value, -1)
            if to_addr != self.zero_addr:
                self.trans(to_addr, value, 1)
        return True

    # calculate total transfer amount
    def get_total_value(self):
        for k, v in self.users_transfer.items():
            if k == self.invest_address:
                continue
            self.total_value += v
        return True

    def get_reward(self, value, addr, percentage=None):
        this_reward = self.liquidity_reward * (value / self.total_value)
        if percentage is not None:
            this_reward = this_reward * Decimal(percentage)
        logger.info('this_reward:{} '.format(this_reward))
        if 'e-' in str(this_reward) or 'E-' in str(this_reward):
            s_reward = ('%.20f' % this_reward).split('.')
        else:
            s_reward = str(this_reward).split('.')
        if len(s_reward) == 1:
            reward = Decimal(s_reward[0])
        else:
            reward = Decimal("{}.{}".format(s_reward[0], s_reward[1][:app_config.EARNINGS_ACCURACY]))
        logger.info('addr: {}, reward: {}'.format(addr, reward))
        return reward

    # calculate rewards
    def earnings(self):
        for addr, value in self.users_transfer.items():
            addr = addr.lower()
            value = Decimal(str(value))
            if addr in list(self.percentage_datas.keys()):
                continue
                # for pa in self.percentage_datas[addr]:
                #     percentage = pa['percentage']
                #     to_addr = pa['to_address']
                #     reward = self.get_reward(value, to_addr, percentage)
                #     if reward == 0:
                #         continue
                #     self.earnings_datas.append({'address': to_addr, 'amount': str(reward)})
            else:
                reward = self.get_reward(value, addr)
                if reward == 0:
                    continue
                self.earnings_datas.append({'address': addr, 'amount': str(reward)})
        return True

    def prepare_datas(self):
        logger.info('wait data:')
        while True:
            if os.path.exists(self.cache_util._yesterday_cache_full_path) \
                    and os.path.exists(os.path.join(self.cache_util._cache_full_path,
                                                    self.cache_util._DAY_AMOUNT_FILE_NAME)):
                time.sleep(1)
                break
            time.sleep(1)
        time.sleep(0.5)
        self.get_datas_from_ipfs()
        self.get_percentage_datas_from_ipfs()
        self.get_new_liquidity_datas()
        self.statistic_user_trans(self.old_trans)
        self.statistic_user_trans(self.new_trans)
        self.get_private_liquidity()
        self.get_total_value()
        today_amount = self.cache_util.get_today_day_amount()
        logger.info('day amount: {}'.format(today_amount))
        self.liquidity_reward = today_amount.get('liquidity_reward', 0)
        return True

    def main(self):
        times = 1
        flag_file_path = os.path.join(self.cache_util._cache_full_path,
                                      self.cache_util._EARNINGS_LIQUIDITY_DATAS_FILE_NAME)
        while True:
            self.init()
            start_timestamp = get_now_timestamp()
            try:
                node_result = self.web3eth.is_senators_or_executer()
                logger.info('self address is : {}'.format(node_result))
                if not node_result:
                    if self.web3eth.check_vote() == 1:
                        return True
                    else:
                        time.sleep(5)
                        continue
                if not os.path.exists(flag_file_path):
                    logger.info('start earnings trans：{}'.format(times))
                    classify = EarningsType.TRANSFER.value
                    haved_earnings_result = check_haved_earnings(logger, flag_file_path, self.web3eth)
                    if haved_earnings_result:
                        logger.info('haved earnings.')
                        return True
                    self.prepare_datas()
                    self.earnings()
                    self.save_today_datas()
                if check_vote(self.web3eth, logger, None, flag_file_path):
                    logger.info('earnings trans success.')
                    return True
                time.sleep(5)
            except:
                logger.error(traceback.format_exc())
                logger.info('earnings trans error.')
            times += 1


logger = logging.getLogger('earnings_trans')


def do():
    TransferEarnings().main()


def earnings():
    while True:
        try:
            hour = app_config.START_HOUR
            minute = app_config.START_MINUTE
            web3eth = Web3Eth(logger)
            latest_proposal = web3eth.get_latest_snapshoot_proposal()
            pagerank_timestamp = datetime_to_timestamp('{} {}:{}:00'.format(get_pagerank_date(), hour, minute))
            if latest_proposal[-1] == 1 and latest_proposal[5] > pagerank_timestamp:
                now_timestamp = get_now_timestamp()
                pagerank_date = get_pagerank_date()
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
                        TransferEarnings().main()
                    else:
                        TransferEarnings().main()
            else:
                logger.info('the previous proposal failed. to run.')
                TransferEarnings().main()
            scheduler.add_job(id='earnings_trans2', func=do, trigger='cron', hour=int(hour), minute=int(minute))
            break
        except:
            logger.error(traceback.format_exc())


logger.info('Earnings trans Job Is Running, pid:{}'.format(os.getpid()))
next_run_time = time_format(timedeltas={"seconds": 20}, opera=1, is_datetime=True)
scheduler.add_job(id='earnings_trans', func=earnings, next_run_time=next_run_time)
