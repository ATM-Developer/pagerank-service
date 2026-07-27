import os
import re
import json
import time
import fcntl
import traceback
from project.extensions import scheduler


def schedulers():
    scheduler.delete_all_jobs()
    from project.jobs import data_job
    from project.jobs import calculate_job
    from project.jobs import earnings_pr_job
    from project.jobs import earnings_pledge_job
    from project.jobs import earnings_trans_job
    from project.jobs import earnings_top_nodes_job
    from project.jobs import liquidity_events_job
    from project.jobs import liquidity_events_usdc_job
    from project.jobs import pledge_events_job
    from project.jobs import prefetching_event_job
    from project.jobs import prefetching_chain_job
    from project.jobs import del_old_datas_job
    from project.jobs import reset_time_job
    # from project.jobs import upgrade_job


lock_file_dir_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'lock_file')
if not os.path.exists(lock_file_dir_path):
    try:
        os.makedirs(lock_file_dir_path)
    except:
        pass


def start_scheduler():
    f = os.popen('ps -aux | grep python')
    result = f.read()
    resultl = result.split('\n')
    p_list = []
    for rl in resultl:
        if '/bin/gunicorn' in rl:
            p_list.append(re.split(' +', rl)[1])
    pid_file_path = os.path.join(lock_file_dir_path, 'scheduler_id.txt')
    pre_pid = None
    pre_ppid = None
    if os.path.exists(pid_file_path):
        with open(pid_file_path, 'r') as rf:
            try:
                data = json.load(rf)
            except:
                data = {}
        pre_pid = data.get('pid')
        pre_ppid = data.get('ppid')
    if os.getppid() == pre_ppid and str(pre_pid) in p_list:
        return True
    try:
        f = open(os.path.join(lock_file_dir_path, 'scheduler_id.txt'), 'w')
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        f.write(json.dumps({'pid': os.getpid(), 'ppid': os.getppid(), 'timestamp': time.time()}))
        f.flush()
        schedulers()
        time.sleep(3)
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()
    except:
        print(traceback.format_exc())
        try:
            f.close()
        except:
            pass


start_scheduler()
