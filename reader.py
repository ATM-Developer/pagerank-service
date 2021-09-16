from utils.eth_util import Web3Eth


class EthDataReader:

    def __init__(self, web3_provider_uri):
        self._web3Eth = Web3Eth(web3_provider_uri)

    def _filter_by_timestamp(self, events, timestamp):
        transaction_list = []
        last_block_number = -1
        for i in range(events.__len__() - 1, -1, -1):
            block_number = events[i]['blockNumber']
            if last_block_number == block_number:
                continue
            else:
                block = self._web3Eth.get_block_by_number(block_number)
                last_block_number = block_number
                if block['timestamp'] >= timestamp:
                    continue
                else:
                    transaction_list = events[:i + 1]
                    break
        return transaction_list, last_block_number

    def prepare_data(self, deadline_timestamp, last_block_number_yesterday):
        latest_block_number = self._web3Eth.get_latest_block_number()
        interval = 5000
        link_created_events = []
        link_active_events = []
        for i in range(last_block_number_yesterday + 1, latest_block_number + 1, interval):
            from_block = i
            to_block = from_block + interval if from_block + interval < latest_block_number else latest_block_number
            # get all link created events
            sub_link_created_events = self._web3Eth.get_factory_link_created_events(from_block, to_block)
            link_created_events.extend(sub_link_created_events)
            # get all link active events
            sub_link_active_events = self._web3Eth.get_factory_link_active_events(from_block, to_block)
            link_active_events.extend(sub_link_active_events)
        # filter link created by deadline
        link_created_transaction_list, link_created_last_block_number = self._filter_by_timestamp(
            link_created_events,
            deadline_timestamp)
        # filter link active by deadline
        link_active_transaction_list, link_active_last_block_number = self._filter_by_timestamp(
            link_active_events,
            deadline_timestamp)
        # prepare info for pg calculate
        recorded = []  # changed data, which isAward_ is False
        recorded_link_set = set()
        unrecorded = []  # new data, which isAward_ is True
        for event in link_active_transaction_list:
            link_address = event['args']['_link']
            if 8 == event['args']['_methodId']:
                link_info = self._web3Eth.get_link_info(link_address)
                recorded.append({'link': link_address, 'userA': link_info.userA_, 'userB': link_info.userB_})
                recorded_link_set.add(link_address)
            elif 5 == event['args']['_methodId']:
                if link_address in recorded_link_set:
                    continue
                else:
                    link_close_info = self._web3Eth.get_link_close_info(link_address)
                    if link_close_info.closeTime_ < deadline_timestamp:
                        link_info = self._web3Eth.get_link_info(link_address)
                        recorded.append({'link': link_address, 'userA': link_info.userA_, 'userB': link_info.userB_})
                        recorded_link_set.add(link_address)
                    else:
                        continue
            else:
                continue
        for event in link_created_transaction_list:
            link_address = event['args']['_link']
            if link_address in recorded_link_set:
                continue
            else:
                # if this link is not in recorded set, it's isAward_ must be True
                link_info = self._web3Eth.get_link_info(link_address)
                if link_info.lockDays_ == 0:
                    print('Invalid lockDays 0 : {}'.format(link_address))
                    continue
                else:
                    info = {'link_contract': link_address, 'symbol_': link_info.symbol_.upper(),
                            'token_': link_info.token_, 'userA_': link_info.userA_, 'userB_': link_info.userB_,
                            'amountA_': link_info.amountA_, 'amountB_': link_info.amountB_,
                            'percentA_': link_info.percentA_, 'totalPlan_': link_info.totalPlan_,
                            'lockDays_': link_info.lockDays_, 'startTime_': link_info.startTime_,
                            'status_': link_info.status_, 'isAward_': True}
                    unrecorded.append(info)
        # last block number
        last_block_number = max(last_block_number_yesterday, link_created_last_block_number,
                                link_active_last_block_number)
        return recorded, unrecorded, last_block_number
