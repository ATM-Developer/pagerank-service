from project.jobs.base_import import *


class PrefetchingChain():
    def __init__(self):
        self.current_address = app_config.WALLET_ADDRESS
        self.current_private_key = app_config.WALLET_PRIVATE_KEY
        self.data_dir = data_dir
        self.temp_file_dir = os.path.join(self.data_dir, 'prefetching_events', 'temp_file')
        self.private_chain = PrivateChain2(logger)
        self.update_top_nodes_start_hour = int(app_config.UPDATE_TOP_NODES_START_HOUR)
        self.update_top_nodes_end_hour = int(app_config.UPDATE_TOP_NODES_END_HOUR)

    def get_datas(self):
        items = []
        data_list = os.listdir(self.temp_file_dir)
        if not data_list:
            return items
        for f in data_list:
            with open(os.path.join(self.temp_file_dir, f), 'r') as rf:
                items.append(json.load(rf))
        return items

    def check_ledger(self, items):
        logger.info('check ledger..')
        ok_list = []
        start_timestamp = time.time()
        while True:
            for i in items:
                addr = i['address']
                nonce = i['nonce']
                if '{}_{}'.format(addr, nonce) in ok_list:
                    continue
                result = self.private_chain.query_vote_result(i['address'], i['nonce'])
                if result:
                    logger.info('{}_{}, ok'.format(addr, nonce))
                    ok_list.append('{}_{}'.format(addr, nonce))
                    os.remove(os.path.join(self.temp_file_dir, '{}_{}.txt'.format(addr, nonce)))
            if len(items) == len(ok_list):
                break
            if time.time() - start_timestamp > 90:
                break
        return True

    def send_to_ledger(self):
        logger.info('send data ->')
        items = self.get_datas()
        logger.info('items len: {}'.format(len(items)))
        if not items:
            return True
        for i in range(len(items) // 20 + 1):
            try:
                self.private_chain.update_ledgers(items[i * 20: i * 20 + 20])
            except Exception as e:
                logger.error(str(e))
                for j in items[i * 20: i * 20 + 20]:
                    try:
                        self.private_chain.update_ledgers([j])
                    except Exception as e:
                        logger.error('error2:{}'.format(str(e)))
        self.check_ledger(items)
        return True

    def update_top_nodes(self, now_datetime):
        logger.info('update top nodes.')
        web3eth = Web3Eth(logger)
        short_timestamp = datetime_to_timestamp('{} {}:{}:00'.format(now_datetime.strftime('%Y-%m-%d'),
                                                                     app_config.START_HOUR, app_config.START_MINUTE))
        logger.info('wait proposal...')
        while True:
            try:
                latest_proposal = web3eth.get_latest_success_snapshoot_proposal()
                proposal_timestamp = latest_proposal[5]
                if proposal_timestamp > short_timestamp:
                    break
                time.sleep(5)
            except:
                time.sleep(5)
            if time_format(is_datetime=True).hour != self.update_top_nodes_start_hour:
                logger.info('time hour !{}.'.format(self.update_top_nodes_start_hour))
                break
        logger.info('haved proposal.')
        top_nodes_info = web3eth.get_top_nodes()
        while True:
            if time_format(is_datetime=True).hour != self.update_top_nodes_start_hour:
                logger.info('time hour !{}.'.format(self.update_top_nodes_start_hour))
                break
            try:
                self.private_chain.update_nodes(top_nodes_info[0])
            except Exception as e:
                logger.error(str(e))
            try:
                end_block_number = self.private_chain.get_latest_block_number()
                result_item = self.private_chain.base_get_events('UpdateNodeAddr',
                                                                 start_block_num=end_block_number - 100,
                                                                 end_block_number=end_block_number, nums=1)
                if result_item:
                    # block_num = result_item[0]['blockNumber']
                    # block_number_info = self.private_chain.get_block_by_number(block_num)
                    # this_timestamp = block_number_info['timestamp']
                    # if this_timestamp > top_nodes_timestamp:
                    break
            except:
                logger.error(traceback.format_exc())
            time.sleep(3)
        logger.info(time_format(is_datetime=True))
        while True:
            if time_format(is_datetime=True).hour != self.update_top_nodes_start_hour:
                break
        return True

    def judge_run(self):
        if not os.path.exists(os.path.join(lock_file_dir_path, 'prefetching_chain_job_run.txt')):
            return False
        with open(os.path.join(lock_file_dir_path, 'prefetching_chain_job_run.txt'), 'r') as rf:
            data = json.load(rf)
        if data['is_run']:
            return True
        return False

    def set_run(self):
        with open(os.path.join(lock_file_dir_path, 'prefetching_chain_job_run.txt'), 'w') as wf:
            json.dump({'is_run': True}, wf)

    def set_not_run(self):
        with open(os.path.join(lock_file_dir_path, 'prefetching_chain_job_run.txt'), 'w') as wf:
            json.dump({'is_run': False}, wf)

    def main(self):
        try:
            logger.info('prefetching data to private chain handler:')
            if self.judge_run():
                logger.info('prefetching data job is running, wait...')
                return True
            self.set_run()
            node_result = self.private_chain.is_node_addr()
            logger.info('node result: {}'.format(node_result))
            if not node_result:
                self.check_ledger(self.get_datas())
                self.set_not_run()
                return False
            now_datetime = time_format(is_datetime=True)
            if now_datetime.hour == self.update_top_nodes_start_hour:
                self.update_top_nodes(now_datetime)
            else:
                self.send_to_ledger()
            self.set_not_run()
            return True
        except Exception as e:
            logger.error(traceback.format_exc())
            self.set_not_run()


logger = logging.getLogger('prefetching_chain')


def prefetching_chain():
    try:
        PrefetchingChain().main()
    except:
        logger.error(traceback.format_exc())


logger.info(' prefetching chain Job Is Running, pid:{}'.format(os.getpid()))
with open(os.path.join(lock_file_dir_path, 'prefetching_chain_job_run.txt'), 'w') as wf:
    json.dump({'is_run': False}, wf)
scheduler.add_job(id='prefetching_chain', func=prefetching_chain, trigger='cron', minute='*/2')
