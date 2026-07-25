from project.jobs.base_import import *
from project.jobs.calculate_boost_job import _most_recent_json, _carve_out_boost_reward

logger = logging.getLogger('reward_boost_pr')

_WAIT_FILES_LOG_INTERVAL = 30


class RewardBoostPr():
    def __init__(self):
        self.web3eth = Web3Eth(logger)
        self.cache_util = CacheUtil()

    def init(self):
        self.reward_datas = []

    def get_reward(self, share, pool):
        this_reward = pool * share
        if 'e-' in str(this_reward) or 'E-' in str(this_reward):
            s_reward = ('%.20f' % this_reward).split('.')
        else:
            s_reward = str(this_reward).split('.')
        if len(s_reward) == 1:
            reward = Decimal(s_reward[0])
        else:
            reward = Decimal('{}.{}'.format(s_reward[0], s_reward[1][:app_config.EARNINGS_ACCURACY]))
        logger.info('this_reward: {}'.format(reward))
        return reward

    def wait_files(self):
        """Waits up to VOTE_EPOCH minutes for pr.json/boost_pr.json/
        day_amount.json, logging which are still missing every
        _WAIT_FILES_LOG_INTERVAL seconds. Returns False on timeout so the
        caller can fall back to the most recent boost_pr.json."""
        required = {
            self.cache_util._PR_FILE_NAME: 'pr.json',
            self.cache_util._BOOST_PR_FILE_NAME: 'boost_pr.json',
            self.cache_util._DAY_AMOUNT_FILE_NAME: 'day_amount.json',
        }
        start_timestamp = get_now_timestamp()
        last_log_timestamp = start_timestamp
        while True:
            missing = [name for fname, name in required.items()
                      if not os.path.exists(os.path.join(self.cache_util._cache_full_path, fname))]
            if not missing:
                time.sleep(1)
                return True
            now_timestamp = get_now_timestamp()
            if now_timestamp - last_log_timestamp >= _WAIT_FILES_LOG_INTERVAL:
                logger.info('still waiting on {} after {}s.'.format(missing, now_timestamp - start_timestamp))
                last_log_timestamp = now_timestamp
            if now_timestamp - start_timestamp > app_config.VOTE_EPOCH * 60:
                logger.info('wait_files timed out - missing {}, falling back to previous boost_pr.json.'
                            .format(missing))
                return False
            time.sleep(1)

    def main(self):
        times = 1
        flag_file_path = os.path.join(self.cache_util._cache_full_path,
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
                    if self.wait_files():
                        boost_pr = self.cache_util.get_today_pr_boost()
                    else:
                        boost_pr, source_date = _most_recent_json(CacheUtil._BOOST_PR_FILE_NAME, logger)
                        logger.info('using boost_pr.json fallback from {}.'.format(source_date))
                    shares = boost_pr.get('shares', {})
                    if shares:
                        # Redo the carve-out (idempotent) in case
                        # calculate_boost_job never ran today at all - else
                        # day_amount.json has no 'boost_reward' key and pool
                        # below reads 0.
                        total_points = Decimal(str(boost_pr.get('total_points', 0)))
                        _carve_out_boost_reward(self.cache_util, logger, total_points)
                        today_amount = self.cache_util.get_today_day_amount()
                        logger.info('day amount: {}'.format(today_amount))
                        pool = today_amount.get('boost_reward', 0)
                        for address, share in shares.items():
                            share = Decimal(str(share))
                            if share <= 0 or pool == 0:
                                continue
                            reward = self.get_reward(share, pool)
                            if reward == 0:
                                continue
                            self.reward_datas.append({'address': address, 'amount': str(reward)})
                    else:
                        logger.info('no boost shares today, no rewards.')
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
