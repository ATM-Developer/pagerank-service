from utils.eth_util import Web3Eth


class EthDataReader:

    def __init__(self, infura_url):
        self._web3Eth = Web3Eth(infura_url)

    def _filter_by_timestamp(self, events, timestamp):
        transaction_list = []
        last_block_number = None
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
        # get all link created events
        link_created_events = self._web3Eth.get_factory_link_created_events(last_block_number_yesterday + 1)
        # filter by deadline
        link_created_transaction_list, link_created_last_block_number = self._filter_by_timestamp(link_created_events,
                                                                                                  deadline_timestamp)
        # get all link active events
        link_active_events = self._web3Eth.get_factory_link_active_events(last_block_number_yesterday + 1)
        # filter by deadline
        link_active_transaction_list, link_active_last_block_number = self._filter_by_timestamp(link_active_events,
                                                                                                deadline_timestamp)
        # prepare info for pg calculate
        recorded = set()  # changed data, which isAward_ is False
        unrecorded = []  # new data, which isAward_ is True
        for event in link_active_transaction_list:
            if 8 == event['args']['_methodId']:
                recorded.add(event['args']['_link'])
            elif 5 == event['args']['_methodId']:
                if event['args']['_link'] in recorded:
                    continue
                else:
                    link_close_info = self._web3Eth.get_link_close_info(event['args']['_link'])
                    if link_close_info.closeTime_ < deadline_timestamp:
                        recorded.add(event['args']['_link'])
                    else:
                        continue
            else:
                continue
        for event in link_created_transaction_list:
            link_address = event['args']['_link']
            if link_address in recorded:
                continue
            else:
                # if this link is not in recorded set, it's isAward_ must be True
                info = {}
                info['link_contract'] = link_address
                link_info = self._web3Eth.get_link_info(link_address)
                info['symbol_'] = link_info.symbol_
                info['token_'] = link_info.token_
                info['userA_'] = link_info.userA_
                info['userB_'] = link_info.userB_
                info['amountA_'] = link_info.amountA_
                info['amountB_'] = link_info.amountB_
                info['percentA_'] = link_info.percentA_
                info['totalPlan_'] = link_info.totalPlan_
                info['lockDays_'] = link_info.lockDays_
                info['startTime_'] = link_info.startTime_
                info['status_'] = link_info.status_
                info['isAward_'] = True
                unrecorded.append(info)
        # last block number
        if link_created_last_block_number < link_active_last_block_number:
            last_block_number = link_active_last_block_number
        else:
            last_block_number = link_created_last_block_number
        return recorded, unrecorded, last_block_number
