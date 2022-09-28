from concurrent.futures import ThreadPoolExecutor
from functools import partial
import traceback
from project.utils.reader_util import EthDataReader


class NftDataReader(EthDataReader):

    def __init__(self, chain='binance', tlogger=None):
        super().__init__(chain, tlogger)

    def prepare_data(self, deadline_timestamp, last_block_number_yesterday):
        latest_block_number = self._web3Eth.get_latest_block_number()
        self.logger.info('{} latest nft block number: {}'.format(self.chain, latest_block_number))
        interval = self._block_range
        link_created_events = []
        link_active_events = []
        for i in range(last_block_number_yesterday, latest_block_number + 1, interval):
            from_block = i
            to_block = from_block + interval - 1 if from_block + interval - 1 < latest_block_number else latest_block_number
            self.logger.info('from block: {}, to block: {}'.format(from_block, to_block))
            # get all link created events
            while True:
                try:
                    sub_link_created_events = self._web3Eth.get_nft_factory_link_created_events(from_block, to_block)
                    link_created_events.extend(sub_link_created_events)
                    break
                except Exception as e:
                    # get events failed
                    self.logger.error(traceback.format_exc())
                    continue
            # get all link active events
            while True:
                try:
                    sub_link_active_events = self._web3Eth.get_nft_factory_link_active_events(from_block, to_block)
                    link_active_events.extend(sub_link_active_events)
                    break
                except Exception as e:
                    # get events failed
                    self.logger.error(traceback.format_exc())
                    continue
        # filter link created by deadline
        link_created_transaction_list, last_invalid_block_number = self._filter_by_events_timestamp(
            link_created_events, deadline_timestamp, latest_block_number + 1)
        # filter link active by deadline
        link_active_transaction_list, last_invalid_block_number = self._filter_by_events_timestamp(
            link_active_events, deadline_timestamp, last_invalid_block_number)
        last_invalid_block_number = self._filter_by_timestamp(last_invalid_block_number, deadline_timestamp)
        self.logger.info('{}: {}'.format(self.chain, last_invalid_block_number))
        # prepare info for pr calculate
        recorded = []  # changed data, which isAward_ is False
        recorded_link_set = set()
        unrecorded = []  # new data, which isAward_ is True
        executor = ThreadPoolExecutor(max_workers=10)
        unrecorded_active_data = []
        link_active_partial_func = partial(self._process_link_active, deadline_timestamp)
        for link_active_info in executor.map(link_active_partial_func, link_active_transaction_list):
            if link_active_info is None:
                continue
            else:
                is_award = link_active_info.get('isAward_', False)
                if is_award:
                    unrecorded_active_data.append(link_active_info)
                else:
                    recorded.append(link_active_info)
                    recorded_link_set.add(link_active_info['link_contract'])
        # remove unrecorded data, which is already in recorded data
        for data in unrecorded_active_data:
            if data['link_contract'] in recorded_link_set:
                continue
            else:
                unrecorded.append(data)
        link_created_partial_func = partial(self._process_link_created, recorded_link_set)
        for link_created_info in executor.map(link_created_partial_func, link_created_transaction_list):
            if link_created_info is None:
                continue
            else:
                unrecorded.append(link_created_info)
        return recorded, unrecorded, last_invalid_block_number

    def _process_link_active(self, deadline_timestamp, event):
        link_address = event['args']['_link']
        # cancel
        if 0 == event['args']['_methodId']:
            return None
        # agree
        elif 1 == event['args']['_methodId']:
            link_info = self._web3Eth.get_nft_link_info(link_address)
            if link_info.lockDays_ == 0:
                self.logger.info('Invalid lockDays 0 : {}'.format(link_address))
                return None
            else:
                info = {'link_contract': link_address, 'nft_': link_info.NFT_,
                        'userA_': link_info.userA_, 'userB_': link_info.userB_,
                        'idA_': link_info.idA_, 'idB_': link_info.idB_,
                        'lockDays_': link_info.lockDays_, 'startTime_': link_info.startTime_,
                        'single': False, 'isAward_': True, 'chain': self.chain}
                return info
        # reject
        elif 2 == event['args']['_methodId']:
            return None
        # close
        elif 3 == event['args']['_methodId']:
            link_info = self._web3Eth.get_nft_link_info(link_address)
            return {'link_contract': link_address, 'userA_': link_info.userA_, 'userB_': link_info.userB_,
                    'isAward_': False, 'chain': self.chain}
        return None

    def _process_link_created(self, recorded_link_set, event):
        link_address = event['args']['link']
        # link is already removed
        if link_address in recorded_link_set:
            return None
        else:
            # userA provides 2 nft
            if 'isFullLink' in event['args'] and event['args']['isFullLink'] is True:
                link_info = self._web3Eth.get_nft_link_info(link_address)
                # lockDays must be bigger than 0
                if link_info.lockDays_ == 0:
                    self.logger.info('Invalid lockDays 0 : {}'.format(link_address))
                    return None
                else:
                    info = {'link_contract': link_address, 'nft_': link_info.NFT_,
                            'userA_': link_info.userA_, 'userB_': link_info.userB_,
                            'idA_': link_info.idA_, 'idB_': link_info.idB_,
                            'lockDays_': link_info.lockDays_, 'startTime_': link_info.startTime_,
                            'single': True, 'isAward_': True, 'chain': self.chain}
                    return info
