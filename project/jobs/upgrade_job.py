# -*- coding=utf-8 -*-
# Date: 2022/8/24 2:06 下午
# Description:

from project.jobs.base_import import *
import subprocess


class UpgradeJob():
    def __init__(self):
        pass

    def main(self):
        this_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
        logger.info('check upgrade process, {}'.format(time_format()))
        with subprocess.Popen('ps -ef | grep ython', shell=True, stdout=subprocess.PIPE) as fp:
            result = fp.stdout.read().decode()
            fp.stdout.close()
        infos = result.split('\n')
        haved = False
        python_v = None
        for info in infos:
            if '{}/upgrade.py'.format(this_path) in info:
                haved = True
            if "bin/gunicorn" in info:
                for j in info.split(' '):
                    if 'ython' in j:
                        logger.info('python version: {}'.format(j))
                        python_v = j
        logger.info('upgrade process status: {}'.format(haved))
        if not haved:
            subprocess.Popen('{} {}/upgrade.py'.format(python_v, this_path), shell=True)
            logger.info('run upgrade process again.')
        return True


def do():
    try:
        UpgradeJob().main()
    except:
        logger.error(traceback.format_exc())


logger = logging.getLogger('upgrade_job')
logger.info('upgrade check process job Is Running, pid:{}'.format(os.getpid()))
scheduler.add_job(id='upgrade_job', func=do, trigger='cron', minute='*/5')
