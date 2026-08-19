from project.jobs.base_import import *
from project.jobs.calculate_boost_job import _most_recent_json, _carve_out_boost_reward, compute_wallet_boost_reward

logger = logging.getLogger('boost_rewards')


class RewardBoostPr():
    def __init__(self):
        self.web3eth = Web3Eth(logger)
        self.cache_util = CacheUtil(hour=app_config.BOOST_START_HOUR, minute=app_config.BOOST_START_MINUTE)

    def init(self):
        self.reward_datas = []

    def wait_files(self):
        required = {
            self.cache_util._PR_FILE_NAME: (os.path.join(data_dir, get_pagerank_date()), 'pr.json'),
            self.cache_util._BOOST_PR_FILE_NAME: (self.cache_util._boost_output_dir(), 'boost_pr.json'),
            self.cache_util._DAY_AMOUNT_FILE_NAME: (self.cache_util._boost_output_dir(), 'day_amount.json'),
        }
        start_timestamp = get_now_timestamp()
        while True:
            missing = [name for fname, (dir_path, name) in required.items()
                      if not os.path.exists(os.path.join(dir_path, fname))]
            if not missing:
                logger.info('wait_files: all files ready after {}s.'.format(get_now_timestamp() - start_timestamp))
                time.sleep(1)
                return True
            if get_now_timestamp() - start_timestamp > app_config.VOTE_EPOCH * 60:
                logger.info('wait_files timed out - still missing {}.'.format(missing))
                return False
            time.sleep(1)

    def main(self):
        times = 1
        flag_file_path = os.path.join(self.cache_util._boost_output_dir(),
                                      self.cache_util._BOOST_REWARD_FILE_NAME)
        while True:
            self.init()
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
                    logger.info('to reward boost pr: {}'.format(times))
                    files_ready = self.wait_files()
                    try:
                        boost_pr = self.cache_util.get_today_pr_boost()
                    except FileNotFoundError:
                        boost_pr = {}
                    if not files_ready and not boost_pr.get('shares'):
                        boost_pr, source_date = _most_recent_json(CacheUtil._BOOST_PR_FILE_NAME, logger)
                        if boost_pr.get('shares'):
                            logger.info('using boost_pr.json fallback from {}.'.format(source_date))
                    shares = boost_pr.get('shares', {})
                    if shares:
                        _carve_out_boost_reward(self.cache_util, logger)
                        today_amount = self.cache_util.get_today_boost_day_amount()
                        logger.info('day amount: {}'.format(today_amount))
                        pool = today_amount.get('boost_reward', 0)
                        for address, share in shares.items():
                            share = Decimal(str(share))
                            if share <= 0 or pool == 0:
                                continue
                            reward = compute_wallet_boost_reward(share, pool)
                            if reward == 0:
                                continue
                            self.reward_datas.append({'address': address, 'amount': str(reward)})
                    else:
                        logger.info('no boost shares today, no rewards.')
                    total_reward = sum(Decimal(r['amount']) for r in self.reward_datas)
                    logger.info('saving boost_reward.json: {} wallets, total {}.'
                                .format(len(self.reward_datas), total_reward))
                    self.cache_util.save_reward_boost(self.reward_datas)
                if check_vote(self.web3eth, logger, None, flag_file_path):
                    logger.info('reward boost pr success.')
                    return True
                time.sleep(5)
            except:
                logger.error(traceback.format_exc())
                logger.info('reward boost pr failure.')
            times += 1


def do():
    RewardBoostPr().main()


def rewards():
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
            scheduler.add_job(id='reward_boost_pr2', func=do, trigger='cron', hour=int(hour), minute=int(minute))
            break
        except:
            logger.error(traceback.format_exc())


logger.info('Reward Boost Pr Job Is Running, pid:{}'.format(os.getpid()))
next_run_time = time_format(timedeltas={'seconds': 20}, opera=1, is_datetime=True)
scheduler.add_job(id='reward_boost_pr', func=rewards, next_run_time=next_run_time)
