from project.jobs.base_import import *
from project.services.pledge_events_service import Handler

logger = logging.getLogger('binance_pledge')


def binance_pledge():
    try:
        handler = Handler('binance', logger)
        handler.get()
        return True
    except:
        logger.error(traceback.format_exc())
        return False


try:
    logger.info('get binance pledge data Job Is Running')
    block_number_path = os.path.join(data_dir, 'pledge_data', 'binance_block_number.txt')
    reset_block_number_file(block_number_path)
    f = open(os.path.join(lock_file_dir_path, 'binance_pledge_data.txt'), 'w')
    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    f.write(str(time.time()))
    scheduler.add_job(id='binance_pledge_data', func=binance_pledge, trigger='cron', minute="*/2")
    time.sleep(3)
    fcntl.flock(f, fcntl.LOCK_UN)
    f.close()
except:
    try:
        f.close()
    except:
        pass
    logger.error(traceback.format_exc())
