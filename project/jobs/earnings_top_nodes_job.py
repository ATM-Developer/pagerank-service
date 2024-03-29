from project.jobs.base_import import *
from project.utils.eth_util import Web3Eth

logger = logging.getLogger('earnings_top_nodes')


class TopNodesEarnings():
    def __init__(self):
        self.web3eth = Web3Eth(logger)
        self.cache_util = CacheUtil()

    def init(self):
        self.earnings_datas = []

    def get_top_nodes(self):
        senators_info = self.cache_util.get_today_senators_info()
        top_nodes = list(senators_info.values()) # earnings to true address
        logger.info('top servers： {}'.format(top_nodes))
        return top_nodes

    def get_reward(self, rewards, earnings_num):
        this_reward = rewards / earnings_num
        if 'e-' in str(this_reward) or 'E-' in str(this_reward):
            s_reward = ('%.20f' % this_reward).split('.')
        else:
            s_reward = str(this_reward).split('.')
        if len(s_reward) == 1:
            reward = Decimal(s_reward[0])
        else:
            reward = Decimal('{}.{}'.format(s_reward[0], s_reward[1][:app_config.EARNINGS_ACCURACY]))
        logger.info('today top servers reward：{}'.format(reward))
        return reward

    def wait_files(self):
        while True:
            if os.path.exists(os.path.join(self.cache_util._cache_full_path, self.cache_util._TOP_NODES_FILE_NAME)) and \
                    os.path.exists(
                        os.path.join(self.cache_util._cache_full_path, self.cache_util._DAY_AMOUNT_FILE_NAME)):
                time.sleep(1)
                break
            time.sleep(1)

    def get_earnings_num(self, top_len):
        return top_len if top_len < app_config.SERVER_NUMBER else app_config.SERVER_NUMBER

    def main(self):
        times = 1
        flag_file_path = os.path.join(self.cache_util._cache_full_path,
                                      self.cache_util._EARNINGS_TOP_NODES_DATAS_FILE_NAME)
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
                    logger.info('to earnings top servers: {}'.format(times))
                    self.wait_files()
                    top_nodes = self.get_top_nodes()
                    if not top_nodes:
                        logger.info('not get top servers, error.')
                        return False
                    result = check_haved_earnings(logger, flag_file_path, self.web3eth)
                    if result:
                        logger.info('haved earnings.')
                        return True
                    today_amount = self.cache_util.get_today_day_amount()
                    logger.info('day amount: {}'.format(today_amount))
                    node_rewards = today_amount.get('node_reward', 0)
                    earnings_num = self.get_earnings_num(len(top_nodes))
                    reward = self.get_reward(node_rewards, earnings_num)
                    earnings_kv = {}
                    for node_address in top_nodes:
                        node_address = node_address.lower()
                        if reward == 0:
                            continue
                        if node_address in earnings_kv:
                            earnings_kv[node_address] += reward
                        else:
                            earnings_kv[node_address] = reward
                    for k, v in earnings_kv.items():
                        self.earnings_datas.append({'address': k, 'amount': str(v)})
                    self.cache_util.save_earnings_top_nodes(self.earnings_datas)
                if check_vote(self.web3eth, logger, None, flag_file_path):
                    logger.info('earnings top servers success.')
                    return True
                time.sleep(5)
            except:
                logger.error(traceback.format_exc())
                logger.info('earnings top servers failure.')
            times += 1


def do():
    TopNodesEarnings().main()


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
            scheduler.add_job(id='earnings_top_nodes2', func=do, trigger='cron', hour=int(hour), minute=int(minute))
            break
        except:
            logger.error(traceback.format_exc())


logger.info('Earnings Top Servers job Is Running:, pid:{}'.format(os.getpid()))
next_run_time = time_format(timedeltas={'seconds': 20}, opera=1, is_datetime=True)
scheduler.add_job(id='earnings_top_nodes', func=earnings, next_run_time=next_run_time)
