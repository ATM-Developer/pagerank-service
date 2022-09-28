from project.jobs.base_import import *
from project.services.pledge_events_service import Handler


def binance_pledge(name, logger):
    try:
        handler = Handler(name, logger)
        handler.get()
        return True
    except:
        logger.error(traceback.format_exc())
        return False


chains = app_config.CHAINS
for name, infos in chains.items():
    if not infos:
        continue
    logger = logging.getLogger('{}_pledge'.format(name))
    logger.info('get {} pledge data Job Is Running, pid:{}'.format(name, os.getpid()))
    block_number_path = os.path.join(data_dir, 'pledge_data', '{}_block_number.txt'.format(name))
    reset_block_number_file(block_number_path)
    scheduler.add_job(id='{}_pledge_data'.format(name), func=binance_pledge, args=[name, logger, ],
                      trigger='cron', minute="*/2")
