from project.jobs.base_import import *


class DelOldData():
    def __init__(self):
        self.data_dir = data_dir

    def del_path(self, fpath):
        if os.path.isdir(fpath):
            shutil.rmtree(fpath)
        else:
            os.remove(fpath)
        logger.info('deleted {}'.format(fpath))

    def del_datas(self, del_date):
        dir_list = os.listdir(self.data_dir)
        for d in dir_list:
            try:
                if d < del_date:
                    d_path = os.path.join(self.data_dir, d)
                    self.del_path(d_path)
            except:
                logger.error(traceback.format_exc())

    def del_liquidity_datas(self, del_date):
        base_path = os.path.join(self.data_dir, "liquidity_data")
        dir_list = os.listdir(base_path)
        for d in dir_list:
            try:
                if d != 'block_number.txt' and d < "data_" + del_date:
                    d_path = os.path.join(base_path, d)
                    self.del_path(d_path)
            except:
                logger.error(traceback.format_exc())

    def del_pledge_datas(self, del_date):
        base_path = os.path.join(self.data_dir, "pledge_data")
        dir_list = os.listdir(base_path)
        for d in dir_list:
            try:
                if d == 'block_number.txt':
                    continue
                if (d.startswith('binance') and d < "binance_" + del_date) or \
                        (d.startswith('matic') and d < "matic_" + del_date):
                    d_path = os.path.join(base_path, d)
                    self.del_path(d_path)
            except:
                logger.error(traceback.format_exc())

    def del_prefetching_events(self, del_date):
        base_path = os.path.join(self.data_dir, "prefetching_events")
        dir_list = os.listdir(base_path)
        for d in dir_list:
            try:
                if d != 'block_number.txt' and d < "data_" + del_date:
                    d_path = os.path.join(base_path, d)
                    self.del_path(d_path)
            except:
                logger.error(traceback.format_exc())

    def del_prefetching_interval(self, del_date):
        pass

    def main(self):
        logger.info('start del:')
        del_datatime = time_format(timedeltas={'days': 30}, opera=-1)
        del_date = del_datatime[:10]
        logger.info('del date is : {}, >=this date will del.'.format(del_date))
        self.del_datas(del_date)
        self.del_liquidity_datas(del_date)
        self.del_pledge_datas(del_date)
        self.del_prefetching_events(del_date)
        logger.info('done.')


def do():
    try:
        DelOldData().main()
        return True
    except:
        logger.error(traceback.format_exc())
        return False


try:
    logger = logging.getLogger('del_old_datas')
    logger.info('del old datas started:')
    f = open(os.path.join(lock_file_dir_path, 'del_old_datas.txt'), 'w')
    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    f.write(str(time.time()))
    hour = app_config.START_HOUR
    scheduler.add_job(id='del_old_datas', func=do, trigger='cron', hour=int(hour) - 1)
    time.sleep(3)
    fcntl.flock(f, fcntl.LOCK_UN)
    f.close()
except:
    try:
        f.close()
    except:
        pass
    logger.error(traceback.format_exc())
