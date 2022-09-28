import os
import sys
import time
import logging
import traceback
import logging.config

logging_json = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(asctime)s - %(levelname)s - [%(funcName)s-%(lineno)s]: %(message)s'
        },
        'thread_': {
            'format': '%(asctime)s - %(levelname)s - %(threadName)s-%(thread)d - [%(funcName)s-%(lineno)s]: %(message)s'
        }
    },
    'handlers': {
        'upgrade': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'thread_',
            'filename': 'log/upgrade.log',
            'maxBytes': 10485760,
            'backupCount': 5,
            'encoding': 'utf8'
        }
    },
    'loggers': {
        'upgrade': {
            'level': 'INFO',
            'handlers': ['upgrade']
        }
    }
}
logging.config.dictConfig(logging_json)
logger = logging.getLogger('upgrade')


class Upgrade():
    def __init__(self):
        self.ssh_agent = self.get_ssh_agent()

    def get_ssh_agent(self):
        with open('manage.py', 'r') as rf:
            manage_info = rf.read()
        domain = 'development'
        for i in manage_info.split('\n'):
            logger.info(i)
            if i.strip().startswith('config_name'):
                domain = i.split('=')[1].strip()[1:-1]
                break
        if domain == 'development':
            ssh_agent = 'eval $(ssh-agent); ssh-add ../id_rsa;'
        else:
            ssh_agent = ''
        logger.info(ssh_agent)
        return ssh_agent

    def get_now_branch(self):
        with os.popen('git branch') as fp:
            result = fp.read()
        branches = result.split('\n')
        for branch in branches:
            if branch.startswith('*'):
                now_branch = branch.replace('*', '').strip()
                return now_branch

    def get_version_id(self):
        logger.info('git log -1')
        with os.popen('git log -1') as fp:
            infos = fp.read().split('\n')
        v_id = infos[0].split(' ')[1]
        return v_id

    def get_remote_info(self, now_branch):
        fp = os.popen('{} git remote show origin'.format(self.ssh_agent))
        result = fp.read()
        logger.info('{}'.format(result))
        infos = result.split('\n')
        for info in infos:
            info = info.strip()
            if info.startswith(now_branch) and (info.endswith('(本地已过时)') or info.endswith('(local out of date)')):
                logger.info('{} local out of date.'.format(now_branch))
                return True
        logger.info('{} up to date.'.format(now_branch))
        return False

    def get_remote_info2(self, now_branch):
        v_id1 = self.get_version_id()
        logger.info('cp project/settings.cfg ../settings.cfg')
        os.system('cp project/settings.cfg ../settings.cfg')
        time.sleep(3)
        logger.info('{} git reset --hard; git pull --rebase'.format(self.ssh_agent))  # todo
        with os.popen('{} git reset --hard; git pull --rebase'.format(self.ssh_agent)) as fp:  # todo
            logger.info('pull: {}'.format(fp.read()))
        time.sleep(10)
        logger.info('cp ../settings.cfg project/settings.cfg')
        os.system('cp ../settings.cfg project/settings.cfg')
        v_id2 = self.get_version_id()
        logger.info('v_id1: {}, v_id2: {}'.format(v_id1, v_id2))
        if v_id1 != v_id2:
            logger.info('{} local out of date.'.format(now_branch))
            return True
        logger.info('{} up to date.'.format(now_branch))
        return False

    def get_hl2(self):
        with os.popen('sudo ps -aux | grep python') as fp:
            haha = fp.read()
        logger.info(haha)
        hl2 = []
        for i in haha.strip().split('\n'):
            if 'gunicorn' in i and 'manage:app' in i:
                hl2.append(i)
        logger.info('hl2', hl2)
        return hl2

    def kill(self):
        logger.info(' - kill:')
        hl2 = self.get_hl2()
        pids = []
        for l2 in hl2:
            p1s = l2.split(' ')
            p1 = ' '.join(p1s[1:]).strip().split(' ')[0]
            pids.append(p1)
        logger.info('ids: {}'.format(pids))
        if pids:
            os.system('sudo kill -9 {}'.format(' '.join([str(i) for i in pids])))

    def pull(self):
        logger.info('sudo cp project/settings.cfg ../settings.cfg')
        os.system('sudo cp project/settings.cfg ../settings.cfg')
        time.sleep(3)
        logger.info('{} git reset --hard; git pull --rebase'.format(self.ssh_agent))
        with os.popen('{} git reset --hard; git pull --rebase'.format(self.ssh_agent)) as fp:
            logger.info('pull: {}'.format(fp.read()))
        time.sleep(10)
        logger.info('sudo cp ../settings.cfg project/settings.cfg')
        with open('../settings.cfg', 'r') as rf:
            old_settings = rf.readlines()
        with open('project/settings.cfg', 'r') as rf:
            new_settings = rf.readlines()
        with open('project/settings.cfg', 'w') as wf:
            wf.write(''.join(old_settings[:6] + new_settings[6:]))

    def restart(self):
        logger.info('sudo gunicorn -t 90 -w 2 -b 0.0.0.0:5000 manage:app -D')
        os.system('sudo gunicorn -t 90 -w 2 -b 0.0.0.0:5000 manage:app -D')
        time.sleep(5)
        if not self.get_hl2():
            logger.info('gunicorn -t 90 -w 2 -b 0.0.0.0:5000 manage:app -D')
            os.system('gunicorn -t 90 -w 2 -b 0.0.0.0:5000 manage:app -D')

    def upgrade(self):
        self.kill()
        time.sleep(5)
        self.pull()
        time.sleep(5)
        self.restart()
        time.sleep(5)
        self.clear_memory()
        logger.info('quit.')
        sys.exit(0)

    def do(self):
        now_branch = self.get_now_branch()
        logger.info('now branch: {}'.format(now_branch))
        if self.get_remote_info(now_branch):
            self.upgrade()

    def clear_memory(self):
        os.system("sudo kill -9 `ps -ef| grep ssh-agent |awk '{print $2}' `")

    def main(self):
        while True:
            logger.info('upgrade, {}'.format(time.strftime('%Y-%m-%d %H:%M:%S')))
            self.do()
            self.clear_memory()
            time.sleep(60 * 2)


Upgrade().main()
