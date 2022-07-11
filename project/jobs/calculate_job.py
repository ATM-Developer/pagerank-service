from project.jobs.base_import import *
from project.utils.calcalate_util import ToCalculate

logger = logging.getLogger('calculate')


class Calculate():
    def __init__(self):
        self.data_file_path = data_dir
        self.today_date = get_pagerank_date()
        self.today_file_path = os.path.join(self.data_file_path, self.today_date)
        self.web3eth = Web3Eth()

    def prepare_datas(self):
        logger.info('prepare datas:')
        yeaterday_datas_path = os.path.join(self.data_file_path, get_previous_pagerank_date())
        while True:
            if os.path.exists(yeaterday_datas_path):
                break
            time.sleep(1)
        time.sleep(0.5)
        coin_list_path = os.path.join(self.data_file_path, self.today_date, CacheUtil._COIN_LIST_FILE_NAME)
        while True:
            if os.path.exists(coin_list_path):
                break
            time.sleep(1)
        time.sleep(0.5)
        coin_price_path = os.path.join(self.data_file_path, self.today_date, CacheUtil._COIN_PRICE_FILE_NAME)
        while True:
            if os.path.exists(coin_price_path):
                break
            time.sleep(1)
        luca_amount_path = os.path.join(self.data_file_path, self.today_date, CacheUtil._LUCA_AMOUNT_FILE_NAME)
        while True:
            if os.path.exists(luca_amount_path):
                break
            time.sleep(1)
        time.sleep(0.5)
        logger.info('prepare datas: ok.')
        return True

    def main(self):
        flag_file_path = os.path.join(self.today_file_path, CacheUtil._PR_FILE_NAME)
        while True:
            try:
                start_timestamp = get_now_timestamp()
                node_result = self.web3eth.is_senators_or_executer()
                logger.info('self address is : {}'.format(node_result))
                if not node_result:
                    latest_proposal = self.web3eth.get_latest_snapshoot_proposal()
                    if latest_proposal[-1] == 1:
                        return True
                    else:
                        time.sleep(5)
                        continue
                if not os.path.exists(flag_file_path):
                    logger.info('once calculate')
                    self.prepare_datas()
                    ToCalculate().run()
                if check_vote(self.web3eth, logger, start_timestamp, flag_file_path):
                    return True
                # if node_result == "is executer":
                #     logger.info('is executer, check vote:')
                #     if check_vote(self.web3eth, logger, start_timestamp):
                #         return True
                #     continue
                # elif node_result == "is senators":
                #     logger.info('is senators, check vote:')
                #     if check_vote(self.web3eth, logger, start_timestamp):
                #         return True
                #     continue
            except:
                logger.error(traceback.format_exc())


def do():
    Calculate().main()


def calculate():
    while True:
        try:
            hour = app_config.START_HOUR
            minute = app_config.START_MINUTE
            web3eth = Web3Eth()
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
                        Calculate().main()
                    else:
                        Calculate().main()
            else:
                logger.info('the previous proposal failed. to run.')
                Calculate().main()
            scheduler.add_job(id='calculate2', func=do, trigger='cron', hour=int(hour), minute=int(minute))
            break
        except:
            logger.error(traceback.format_exc())


logger.info('Calculate Job Is Running, pid:{}'.format(os.getpid()))
next_run_time = time_format(timedeltas={"seconds": 20}, opera=1, is_datetime=True)
scheduler.add_job(id='calculate', func=calculate, next_run_time=next_run_time)
