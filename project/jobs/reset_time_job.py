from project.jobs.base_import import *
import ntplib


def do():
    c = ntplib.NTPClient()
    response = c.request('pool.ntp.org')
    ts = response.tx_time
    datetime = timestamp_to_format2(ts)
    os.system('sudo date -s "{}.{}"'.format(datetime, str(ts).split('.')[1]))
    logger.info('reset time ok. set ts datetime')


logger = logging.getLogger('reset_time')
try:
    logger.info('Reset Time job Is Running, pid:{}'.format(os.getppid()))
    f = open(os.path.join(lock_file_dir_path, 'reset_time.txt'), 'w')
    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    f.write(str(time.time()))
    scheduler.add_job(id='reset_time', func=do, trigger='cron', hour=20)
    time.sleep(3)
    fcntl.flock(f, fcntl.LOCK_UN)
    f.close()
except:
    try:
        f.close()
    except:
        pass
    logger.error(traceback.format_exc())
