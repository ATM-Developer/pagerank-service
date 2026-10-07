# -*- encoding: utf-8 -*-

from project.models.entity import TbVoucherSettled
from project.jobs.base_events_job import *
from project.utils.voucher_calculate_util import configured_voucher_events


class Handler(BaseEventsHandler):
    def archive_cursor_file(self):
        return CacheUtil._VOUCHER_INCENTIVE_BLOCK_NUMBER_FILE_NAME

    def archive_cursor_block(self, block_data):
        return block_data.get(self.event_name)

    def event_to_item(self, data):
        log_index = data['logIndex']
        to = data['args']['to'].lower()
        voucher_type = data['args']['voucherType']
        mode = data['args']['mode']
        is_credit = data['args']['isCredit']
        token_standard = data['args']['tokenStandard']
        token = data['args']['token'].lower()
        token_id = data['args']['tokenId']
        amount = data['args']['amount']
        redemption_days = data['args']['redemptionDays']
        expiry_date = data['args']['expiryDate']
        event_time = data['timestamp']
        transaction_index = data['transactionIndex']
        transaction_hash = data['transactionHash'].hex()
        address = data['address']
        block_hash = data['blockHash'].hex()
        block_number = data['blockNumber']
        event = data['event']
        item = TbVoucherSettled(self.chain, to, voucher_type, mode, is_credit, token_standard, token, token_id,
                                 amount, redemption_days, expiry_date, event_time, transaction_index,
                                 transaction_hash, address, block_hash, block_number, event, log_index).to_dict()
        item['_time'] = event_time
        self.items.append(item)

    def get_events_datas(self, start_block, end_block, retry_times):
        return self.web3eth.get_voucher_settled_events(start_block, end_block, self.contract_address, self.abi, retry_times)


class _EventLogger(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return '[{}] {}'.format(self.extra['event_name'], msg), kwargs


def make_job(event_name):
    logger = _EventLogger(logging.getLogger('voucher_data'), {'event_name': event_name})

    def get_voucher_incentive_data():
        try:
            handler = Handler(event_name, logger)
            handler.get()
        except:
            logger.error(traceback.format_exc())

    logger.info('get {} Job Is Running, pid:{}'.format(event_name, os.getpid()))
    block_number_path = os.path.join(data_dir, event_name, 'block_number.txt')
    reset_block_number_file(block_number_path, logger)
    scheduler.add_job(id=event_name, func=get_voucher_incentive_data, trigger='cron', minute="*/2")


for event_name in configured_voucher_events(logging.getLogger('voucher_data')):
    make_job(event_name)
