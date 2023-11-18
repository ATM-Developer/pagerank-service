from project.jobs.base_import import *


# calculate pledge rewards
class PledgeEarnings():
    def __init__(self):
        self.data_file_path = data_dir
        self.cache_util = CacheUtil()

    def init(self):
        self.top_nodes_pledges = {}
        self.users_pledge_top_nodes = {}
        self.all_total_pledge = 0

        self.old_pledge_datas = []
        self.web3eth = Web3Eth(logger)
        self.new_pledge_datas = []
        # self.binance_end_block_number = 0
        # self.matic_end_block_number = 0
        self.end_block_number = {}
        self.pledge_reward = 0
        self.earnings_datas = []

    def get_datas_from_ipfs(self):
        self.old_pledge_datas = self.cache_util.get_cache_pledge_datas()
        return True

    def get_new_pledge_datas2(self):
        chains = app_config.CHAINS
        pagerank_date = get_pagerank_date()
        for name in chains.keys():
            new_data_file_path = os.path.join(self.data_file_path, 'pledge_data',
                                              '{}_{}.txt'.format(name, pagerank_date))
            if not chains[name] and not os.path.exists(new_data_file_path):
                continue
            with open(new_data_file_path, 'r') as rf:
                for item in rf.readlines():
                    if item.strip():
                        json_item = json.loads(item.strip())
                        if json_item not in self.new_pledge_datas:
                            self.new_pledge_datas.append(json_item)
            new_blockbu_file_path = os.path.join(self.data_file_path, 'pledge_data',
                                                 '{}_{}_end_block.txt'.format(name, pagerank_date))
            if not chains[name] and not os.path.exists(new_blockbu_file_path):
                continue
            with open(new_blockbu_file_path, 'r') as rf:
                block_data = json.load(rf)
            self.end_block_number['{}_pledge'.format(name)] = block_data['block']
        self.new_pledge_datas = sorted(self.new_pledge_datas, key=lambda x: x['date'])
        return True

    def save_today_datas(self):
        self.cache_util.save_pledge_datas(self.old_pledge_datas + self.new_pledge_datas)
        self.cache_util.save_pledge_block_number(self.end_block_number)
        self.cache_util.save_earnings_pledge(self.earnings_datas)
        return True

    def statistic_amount(self, user_address, luca_type, amount, stype=1):
        """

        :param stype: 1 means +；-1 means -
        :return:
        """
        amount = Decimal(str(amount))
        amount *= stype
        user_address = user_address.lower()
        try:
            self.users_pledge_top_nodes[user_address][luca_type] += amount
        except:
            try:
                self.users_pledge_top_nodes[user_address][luca_type] = amount
            except:
                self.users_pledge_top_nodes[user_address] = {}
                self.users_pledge_top_nodes[user_address][luca_type] = amount
        return True

    def luca_2_wluca(self):
        to_luca_proportion = self.web3eth.get_to_wluca_proportion()
        for user_address, amounts in self.users_pledge_top_nodes.items():
            total_wluca = Decimal(str(amounts.get('luca', 0))) * Decimal(str(to_luca_proportion)) \
                          + Decimal(str(amounts.get('wluca', 0)))
            amounts['total_wluca'] = total_wluca
        return True

    # query all pledge data
    def get_users_total_pledges(self):
        for data in self.old_pledge_datas:
            try:
                self.top_nodes_pledges[data['user_address']][
                    '{}_{}'.format(data['stake_num'], data['event'])] = data
            except:
                self.top_nodes_pledges[data['user_address']] = {}
                self.top_nodes_pledges[data['user_address']][
                    '{}_{}'.format(data['stake_num'], data['event'])] = data
        for data in self.new_pledge_datas:
            try:
                self.top_nodes_pledges[data['user_address']][
                    '{}_{}'.format(data['stake_num'], data['event'])] = data
            except:
                self.top_nodes_pledges[data['user_address']] = {}
                self.top_nodes_pledges[data['user_address']][
                    '{}_{}'.format(data['stake_num'], data['event'])] = data
        for addr, datas in self.top_nodes_pledges.items():
            for k, item in datas.items():
                event = item['event']
                event_name = event.split("_")[0]
                amount = item['amount']
                user_addr = item['user_address']

                if event_name == 'StakeLuca':
                    self.statistic_amount(user_addr, 'luca', amount)
                elif event_name == 'StakeWLuca':
                    self.statistic_amount(user_addr, 'wluca', amount)
                elif event_name == 'EndStakeLuca':
                    stake_num = item['stake_num']
                    stake_item = datas['{}_{}'.format(stake_num, event[3:])]
                    amount = stake_item['amount']
                    self.statistic_amount(user_addr, 'luca', amount, stype=-1)
                elif event_name == 'EndStakeWLuca':
                    stake_num = item['stake_num']
                    stake_item = datas['{}_{}'.format(stake_num, event[3:])]
                    amount = stake_item['amount']
                    self.statistic_amount(user_addr, 'wluca', amount, stype=-1)
        self.luca_2_wluca()
        return True

    # calculate pledge rewards
    def get_reward(self, user_total_pledge, addr):
        if user_total_pledge == 0:
            return 0
        this_reward = self.pledge_reward * user_total_pledge / self.all_total_pledge
        logger.info('addr: {}, this_reward: {}'.format(addr, this_reward))
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
        # self.get_new_pledge_datas()
        # self.get_new_matic_pledge_datas()
        self.get_new_pledge_datas2()
        self.get_users_total_pledges()

        for address, amounts in self.users_pledge_top_nodes.items():
            self.all_total_pledge += amounts['total_wluca']
        today_amount = self.cache_util.get_today_day_amount()
        logger.info('today amount: {}'.format(today_amount))
        self.pledge_reward = today_amount.get('pledge_reward', 0)
        return True

    def main(self):
        times = 1
        flag_file_path = os.path.join(self.cache_util._cache_full_path,
                                      self.cache_util._EARNINGS_PLEDGE_DATAS_FILE_NAME)
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
                    logger.info('start earnings pledge：{}'.format(times))
                    classify = EarningsType.PLEDGE.value
                    haved_earnings_result = check_haved_earnings(logger, flag_file_path, self.web3eth)
                    if haved_earnings_result:
                        logger.info('haved earnings')
                        return True
                    self.prepare_datas()
                    for address, amounts in self.users_pledge_top_nodes.items():
                        address = address.lower()
                        reward = self.get_reward(amounts['total_wluca'], address)
                        if reward == 0:
                            continue
                        self.earnings_datas.append({"address": address, "amount": str(reward)})
                    self.save_today_datas()
                if check_vote(self.web3eth, logger, None, flag_file_path):
                    logger.info('earnings pledge success.')
                    return True
                time.sleep(5)
            except:
                logger.error(traceback.format_exc())
                logger.info('earnings pledge error.')
            times += 1


logger = logging.getLogger('earnings_pledge')


def do():
    PledgeEarnings().main()


def earnings():
    while True:
        try:
            hour = app_config.START_HOUR
            minute = app_config.START_MINUTE
            web3eth = Web3Eth(logger)
            latest_proposal = web3eth.get_latest_snapshoot_proposal()
            pagerank_date = get_pagerank_date()
            pagerank_timestamp = datetime_to_timestamp('{} {}:{}:00'.format(pagerank_date, hour, minute))
            if latest_proposal[-1] == 1 and latest_proposal[5] > pagerank_timestamp:
                now_timestamp = get_now_timestamp()
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
                        do()
                    else:
                        do()
            else:
                logger.info('the previous proposal failed. to run.')
                do()
            scheduler.add_job(id='earnings_pledge2', func=do, trigger='cron', hour=int(hour), minute=int(minute))
            break
        except:
            logger.error(traceback.format_exc())


logger.info('Earnings pledge Job Is Running, pid:{}'.format(os.getpid()))
next_run_time = time_format(timedeltas={"seconds": 20}, opera=1, is_datetime=True)
scheduler.add_job(id='earnings_pledge', func=earnings, next_run_time=next_run_time)
