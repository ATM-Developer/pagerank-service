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
logger.info('Reset Time job Is Running, pid:{}'.format(os.getpid()))
scheduler.add_job(id='reset_time', func=do, trigger='cron', hour=20)
