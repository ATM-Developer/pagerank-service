from project.jobs.base_import import *
from project.utils.voucher_calculate_util import ToCalculate as VoucherToCalculate, launched_voucher_events, \
    voucher_end_block_path


class VoucherReward():
    def __init__(self):
        self.cache_util = CacheUtil()

    def init(self):
        self.web3eth = Web3Eth(logger)
        self.chain_web3eth = {}

    def day_changed(self, pagerank_date):
        if get_pagerank_date() != pagerank_date:
            logger.info('pagerank date moved on from {} while waiting, abandoning this run.'.format(pagerank_date))
            return True
        return False

    def prepare_datas(self):
        pagerank_date = get_pagerank_date()
        logger.info('wait data:')
        while True:
            if self.day_changed(pagerank_date):
                return False
            if os.path.exists(self.cache_util._yesterday_cache_full_path) \
                    and os.path.exists(os.path.join(self.cache_util._cache_full_path,
                                                    self.cache_util._DAY_AMOUNT_FILE_NAME)):
                time.sleep(1)
                break
            time.sleep(1)
        cutoff = datetime_to_timestamp('{} {}:{}:00'.format(
            pagerank_date, app_config.OTHER_HOUR, app_config.OTHER_MINUTE))
        while not self.events_complete(cutoff, pagerank_date):
            if self.day_changed(pagerank_date):
                return False
            time.sleep(10)
        time.sleep(0.5)
        return True

    def events_complete(self, cutoff, pagerank_date):
        for event_name in launched_voucher_events(pagerank_date, logger):
            block_number_path = os.path.join(data_dir, event_name, 'block_number.txt')
            try:
                with open(block_number_path, 'r') as rf:
                    block = json.loads(rf.read().strip()).get('block')
                chain = app_config.EVENTS[event_name]['CHAIN']
                if chain not in self.chain_web3eth:
                    self.chain_web3eth[chain] = Web3Eth(logger, chain)
                block_timestamp = self.chain_web3eth[chain].get_block_by_number(block)['timestamp']
            except:
                logger.info('{} events cursor not readable yet, wait.'.format(event_name))
                return False
            if block_timestamp < cutoff:
                logger.info('{} events scanned to block {} ({}), before cutoff {}, wait.'.format(
                    event_name, block, block_timestamp, cutoff))
                return False
            if not os.path.exists(voucher_end_block_path(data_dir, event_name, pagerank_date)):
                logger.info('{} end block for {} not written yet, wait.'.format(event_name, pagerank_date))
                return False
        return True

    def main(self):
        times = 1
        flag_file_path = os.path.join(self.cache_util._cache_full_path,
                                      self.cache_util._VOUCHER_REWARD_TOTAL_FILE_NAME)
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
                    logger.info('start voucher reward：{}'.format(times))
                    already_done = check_haved_earnings(logger, flag_file_path, self.web3eth)
                    if already_done:
                        logger.info('voucher reward already done')
                        return True
                    if not self.prepare_datas():
                        return False
                    VoucherToCalculate().calculate()
                if check_vote(self.web3eth, logger, None, flag_file_path):
                    logger.info('voucher reward success.')
                    return True
                time.sleep(5)
            except:
                logger.error(traceback.format_exc())
                logger.info('voucher reward error.')
            times += 1


logger = logging.getLogger('voucher_incentive_calculate')


def do():
    VoucherReward().main()


def reward():
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
            scheduler.add_job(id='voucher_reward2', func=do, trigger='cron', hour=int(hour), minute=int(minute))
            break
        except:
            logger.error(traceback.format_exc())


logger.info('Voucher reward Job Is Running, pid:{}'.format(os.getpid()))
next_run_time = time_format(timedeltas={"seconds": 20}, opera=1, is_datetime=True)
scheduler.add_job(id='voucher_reward', func=reward, next_run_time=next_run_time)
