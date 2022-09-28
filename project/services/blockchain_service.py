import time


def get_yesterday_file_id(web3eth, timestamp):
    while True:
        try:
            res = web3eth.get_latest_success_snapshoot_proposal()
            if res[-2] < timestamp:
                continue
            return res[3]
        except:
            time.sleep(1)
