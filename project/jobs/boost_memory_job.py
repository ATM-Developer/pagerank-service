from project.jobs.base_import import *
from project.utils.game_hub_util import GameHubReader

logger = logging.getLogger('boost_memory')


class BoostMemory():
    def __init__(self):
        self.data_file_path = data_dir
        # Boost runs on its own cutoff (BOOST_START_HOUR/MINUTE), not the
        # main PR job's.
        self.today_date = get_pagerank_date(app_config.BOOST_START_HOUR, app_config.BOOST_START_MINUTE)
        self.today_file_path = os.path.join(self.data_file_path, self.today_date)
        self.web3eth = Web3Eth(logger)
        self.cache_util = CacheUtil(hour=app_config.BOOST_START_HOUR, minute=app_config.BOOST_START_MINUTE)

    def main(self):
        flag_file_path = os.path.join(self.today_file_path, CacheUtil._BOOST_MEMORY_FILE_NAME)
        times = 1
        while True:
            try:
                start_timestamp = get_now_timestamp()
                logger.info('boost memory times: {}, time: {}'.format(times, start_timestamp))
                node_result = self.web3eth.is_senators_or_executer()
                logger.info('self address is : {}'.format(node_result))
                if not node_result:
                    if self.web3eth.check_vote() == 1:
                        return True
                    else:
                        time.sleep(5)
                        continue
                logger.info('fetch boost memory data.')
                fetch_start_timestamp = get_now_timestamp()
                # Re-fetch every pass (not just once) so a gap-backfill can
                # still trigger later; base off today's own file once it
                # exists so a later pass doesn't discard today's progress.
                memory = self.cache_util.get_today_boost_memory() if os.path.exists(flag_file_path) \
                    else self.cache_util.get_boost_memory()
                rows, memory = GameHubReader(logger).fetch_all(
                    memory, on_progress=self.cache_util.save_boost_memory)
                logger.info('boost rows count: {}, fetch took {:.2f}s'
                           .format(len(rows), get_now_timestamp() - fetch_start_timestamp))
                self.cache_util.save_boost_memory(memory)
                if check_vote(self.web3eth, logger, self.today_date, flag_file_path):
                    return True
            except:
                logger.error(traceback.format_exc())
                time.sleep(5)
            times += 1


def do():
    BoostMemory().main()


def boost_memory():
    while True:
        try:
            hour = app_config.BOOST_START_HOUR
            minute = app_config.BOOST_START_MINUTE
            web3eth = Web3Eth(logger)
            latest_proposal = web3eth.get_latest_snapshoot_proposal()
            pagerank_date = get_pagerank_date()
            pagerank_timestamp = datetime_to_timestamp('{} {}:{}:00'.format(pagerank_date,
                                                                            app_config.START_HOUR,
                                                                            app_config.START_MINUTE))
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
            scheduler.add_job(id='boost_memory2', func=do, trigger='cron', hour=int(hour), minute=int(minute))
            break
        except:
            logger.error(traceback.format_exc())


logger.info('Boost Memory Job Is Running, pid:{}'.format(os.getpid()))
next_run_time = time_format(timedeltas={"seconds": 20}, opera=1, is_datetime=True)
scheduler.add_job(id='boost_memory', func=boost_memory, next_run_time=next_run_time)
