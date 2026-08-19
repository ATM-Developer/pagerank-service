from project.jobs.base_import import *

logger = logging.getLogger('boost_ledger_purge')


class BoostLedgerPurge():
    def __init__(self):
        self.boost_data_root = os.path.join(data_dir, CacheUtil._BOOST_DATA_ROOT_DIR)

    def main(self):
        logger.info('start boost ledger purge:')
        if not os.path.isdir(self.boost_data_root):
            logger.info('no boost_data/ directory yet - nothing to purge.')
            return True
        retention_days = int(app_config.BOOST_LEDGER_RETENTION_DAYS)
        cutoff_date = time_format(timedeltas={'days': retention_days}, opera=-1)[:10]
        deleted = 0
        for entry in os.listdir(self.boost_data_root):
            entry_path = os.path.join(self.boost_data_root, entry)
            if not os.path.isdir(entry_path):
                continue
            if len(entry) != 10 or entry[4] != '-' or entry[7] != '-':
                continue
            if entry <= cutoff_date:
                shutil.rmtree(entry_path)
                deleted += 1
                logger.info('deleted boost_data/{} (older than retention cutoff {}).'.format(entry, cutoff_date))
        logger.info('done - deleted {} boost_data date folder(s), cutoff {}.'.format(deleted, cutoff_date))
        return True


def do():
    try:
        BoostLedgerPurge().main()
        return True
    except:
        logger.error(traceback.format_exc())
        return False


logger.info('boost ledger purge job started, pid:{}'.format(os.getpid()))
hour = app_config.START_HOUR
scheduler.add_job(id='boost_ledger_purge', func=do, trigger='cron', hour=int(hour) - 1, minute=30)
