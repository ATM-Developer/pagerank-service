import time
from project.utils.eth_util import Web3Eth


def get_yesterday_file_id(logger, timestamp):
    while True:
        try:
            res = Web3Eth(logger).get_latest_success_snapshoot_proposal()
            if res[-2] < timestamp:
                continue
            return res[3]
        except:
            time.sleep(1)
