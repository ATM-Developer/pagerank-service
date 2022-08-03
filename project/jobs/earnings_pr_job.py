from project.jobs.base_import import *


class PREarnings():
    def __init__(self, logger, earnings_type, rewards_item, pr_file_path):
        self.logger = logger
        self.earnings_type = earnings_type
        self.file_path = pr_file_path
        self.datas = {}  # PR data
        self.rewards_item = rewards_item

    def get_pr_data2(self):
        with open(self.file_path, 'r') as rf:
            self.datas = json.loads(rf.read().strip())

    def handler(self):
        try:
            self.get_pr_data2()
            total_count = 0
            rewards = {}
            if self.earnings_type == EarningsType.PR.value:
                rewards = {}
                v = self.rewards_item.get('pr_reward', '0')
                if v > 0:
                    rewards['luca'] = v
            elif self.earnings_type == EarningsType.NET_PR.value:
                rewards = {}
                for k, v in self.rewards_item.items():
                    if k.endswith('_net') and v > 0:
                        rewards[k.rsplit('_')[0]] = v
            elif self.earnings_type == EarningsType.ALONE_PR.value:
                rewards = {}
                for k, v in self.rewards_item.items():
                    if k.endswith('_alone') and v > 0:
                        rewards[k.rsplit('_')[0]] = v
            self.logger.info('{} rewards: {}'.format(self.earnings_type, rewards))
            if not rewards:
                self.logger.info('{} not get rewards items, no earnings.'.format(self.earnings_type))
                if self.earnings_type == EarningsType.PR.value:
                    CacheUtil().save_earnings_main_pr([])
                elif self.earnings_type == EarningsType.NET_PR.value:
                    CacheUtil().save_earnings_net_pr([])
                elif self.earnings_type == EarningsType.ALONE_PR.value:
                    CacheUtil().save_earnings_alone_pr([])
                return True
            for coin_type, address_pr in self.datas.items():
                if self.earnings_type == EarningsType.ALONE_PR.value:
                    v = rewards.get(coin_type.lower(), 0)
                    if v <= 0:
                        continue
                    this_rewards = {coin_type.lower(): v}
                else:
                    if coin_type.lower() != 'mainnet':
                        continue
                    this_rewards = rewards
                total_count += len(address_pr) * len(list(this_rewards.keys()))
                PREarningModule(address_pr, this_rewards, self.earnings_type, self.logger).main()

            self.logger.info('earnings {} pr success, count: {}'.format(self.earnings_type, total_count))
            return True
        except:
            self.logger.error(traceback.format_exc())
            return False

    def main(self):
        try:
            result = check_haved_earnings(self.logger,
                                          '/'.join(self.file_path.split('/')[:-1]
                                                   + ['earnings_{}.json'.format(self.earnings_type)]))
            if result:
                self.logger.info('{} haved earnings.'.format(self.earnings_type))
                return True
            if self.handler():
                self.logger.info('{} earnings success.'.format(self.earnings_type))
            else:
                self.logger.info('{} earnings failed.'.format(self.earnings_type))
            return True
        except:
            self.logger.error(traceback.format_exc())
            self.logger.info('{} earnings error.'.format(self.earnings_type))


class PREarningModule():
    def __init__(self, datas, rewards, earnings_type, logger):
        self.logger = logger
        self.datas = datas
        self.rewards = rewards
        for k, v in self.rewards.items():
            self.rewards[k] = Decimal(v)
        self.earnings_type = earnings_type
        self.earnings_data = []

    # calculate pr rewards
    def get_reward(self, pr, user_address, coin_reward, coin):
        this_reward = Decimal(str(pr)) * coin_reward
        if 'e-' in str(this_reward) or 'E-' in str(this_reward):
            s_reward = ('%.20f' % this_reward).split('.')
        else:
            s_reward = str(this_reward).split('.')
        if len(s_reward) == 1:
            reward = Decimal(s_reward[0])
        else:
            reward = Decimal('{}.{}'.format(s_reward[0], s_reward[1][:app_config.EARNINGS_ACCURACY]))
        self.logger.info('user_address: {}, {} earnings: {}'.format(user_address, coin, reward))
        return reward

    def save_to_file(self):
        if self.earnings_type == EarningsType.PR.value:
            CacheUtil().save_earnings_main_pr(self.earnings_data)
        elif self.earnings_type == EarningsType.NET_PR.value:
            CacheUtil().save_earnings_net_pr(self.earnings_data)
        elif self.earnings_type == EarningsType.ALONE_PR.value:
            CacheUtil().save_earnings_alone_pr(self.earnings_data)
        return True

    def main(self):
        try:
            for address, pr in self.datas.items():
                address = address.lower()
                for coin, coin_reward in self.rewards.items():
                    if coin_reward == 0:
                        continue
                    amount = self.get_reward(pr, address, coin_reward, coin)
                    if amount == 0:
                        continue
                    self.earnings_data.append({'address': address, 'amount': str(amount), 'coin': coin})
            self.save_to_file()
        except:
            self.logger.error(traceback.format_exc())


logger = logging.getLogger('earnings_pr')


def earnings_maincoin_pr(rewards_item, pr_file_path):
    logger.info('start earnings main coin pr.')
    # rewards of pr
    PREarnings(logger, EarningsType.PR.value, rewards_item, pr_file_path).main()
    return True


def earnings_net_pr(rewards_item, pr_file_path):
    # rewards of net_pr
    net_pr_logger = logging.getLogger('earnings_net_pr')
    net_pr_logger.info('start earnings subcoin net pr.')
    PREarnings(net_pr_logger, EarningsType.NET_PR.value, rewards_item, pr_file_path).main()
    return True


def earnings_alone_pr(rewards_item, pr_file_path):
    # rewards of alone_pr
    alone_pr_logger = logging.getLogger('earnings_alone_pr')
    alone_pr_logger.info('start earnings subcoin alone pr.')
    PREarnings(alone_pr_logger, EarningsType.ALONE_PR.value, rewards_item, pr_file_path).main()
    return True


class Main():
    def __init__(self):
        self.web3eth = Web3Eth(logger)
        self.cache_util = CacheUtil()
        self.pr_file_path = os.path.join(self.cache_util._cache_full_path, self.cache_util._PR_FILE_NAME)

    def go(self, rewards_item):
        run_time = time_format(timedeltas={'seconds': 30}, opera=1, is_datetime=True)
        scheduler.add_job(id='earnings_maincoin_pr', func=earnings_maincoin_pr,
                          args=[rewards_item, self.pr_file_path, ], next_run_time=run_time)
        scheduler.add_job(id='earnings_subcoin_net_pr', func=earnings_net_pr, args=[rewards_item, self.pr_file_path, ],
                          next_run_time=run_time)
        scheduler.add_job(id='earnings_subcoin_alone_pr', func=earnings_alone_pr,
                          args=[rewards_item, self.pr_file_path, ], next_run_time=run_time)

    def go2(self, rewards_item):
        with ThreadPoolExecutor(max_workers=3) as executer:
            futures = [
                executer.submit(earnings_maincoin_pr, rewards_item, self.pr_file_path),
                executer.submit(earnings_net_pr, rewards_item, self.pr_file_path),
                executer.submit(earnings_alone_pr, rewards_item, self.pr_file_path)
            ]
            wait(futures, return_when=ALL_COMPLETED)
        return True

    def main(self):
        times = 1
        flag_file_path = os.path.join(self.cache_util._cache_full_path,
                                      self.cache_util._EARNINGS_MAIN_PR_DATAS_FILE_NAME)
        while True:
            start_timestamp = get_now_timestamp()
            try:
                node_result = self.web3eth.is_senators_or_executer()
                logger.info('self address is : {}'.format(node_result))
                if not node_result:
                    latest_proposal = self.web3eth.get_latest_snapshoot_proposal()
                    if latest_proposal[-1] == 1:
                        return True
                    else:
                        time.sleep(5)
                        continue
                logger.info('wait data:')
                while True:
                    if os.path.exists(self.pr_file_path) \
                            and os.path.exists(os.path.join(self.cache_util._cache_full_path,
                                                            self.cache_util._DAY_AMOUNT_FILE_NAME)):
                        time.sleep(1)
                        break
                    time.sleep(1)
                if not os.path.exists(flag_file_path):
                    rewards_item = self.cache_util.get_today_day_amount()
                    logger.info('day amount: {}'.format(rewards_item))
                    self.go2(rewards_item)

                if check_vote(self.web3eth, logger, start_timestamp, flag_file_path):
                    logger.info('earnings pr success.')
                    return True
                time.sleep(5)
            except:
                logger.error(traceback.format_exc())
            times += 1


def do():
    Main().main()


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
                        Main().main()
                    else:
                        Main().main()
            else:
                logger.info('the previous proposal failed. to run.')
                Main().main()
            scheduler.add_job(id='earnings_pr2', func=do, trigger='cron', hour=int(hour), minute=int(minute))
            break
        except:
            logger.error(traceback.format_exc())


logger.info('Earnings pr job Is Running, pid:{}'.format(os.getpid()))
next_run_time = time_format(timedeltas={'seconds': 20}, opera=1, is_datetime=True)
scheduler.add_job(id='earnings_pr', func=earnings, next_run_time=next_run_time)
