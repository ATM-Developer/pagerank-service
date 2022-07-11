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


logger.info('get binance pledge data Job Is Running, pid:{}'.format(os.getpid()))
block_number_path = os.path.join(data_dir, 'pledge_data', 'binance_block_number.txt')
reset_block_number_file(block_number_path)
scheduler.add_job(id='binance_pledge_data', func=binance_pledge, trigger='cron', minute="*/2")
