import os
from web3 import Web3
from Configs.eth.eth_config import FACTORY_ADDRESS, FACTORY_ABI, LINK_ABI


def prepare_data(infura_url):
    w3 = Web3(Web3.HTTPProvider(infura_url))
    factory_contract = w3.eth.contract(FACTORY_ADDRESS, abi=FACTORY_ABI)

    # hex-->dec
    def decize(hex):
        dec = '0x' + hex[26:]
        return dec

    # execute the filter
    _filter = factory_contract.events.LinkCreated.createFilter(
        fromBlock=0, toBlock='latest')
    transcation_list = _filter.get_all_entries()

    # prepare info for pg calculate
    info_list = []
    # prepare transactionHash_list for last_day record checking
    transactionHash_list = []

    for i in transcation_list:
        transactionHash_list.append(i['transactionHash'].hex())
        info = {}
        # 目前只能通过 index=[-1]来筛选出link-created event
        # link_add = w3.eth.get_transaction_receipt(i['transactionHash'])['logs'][-1]['data']
        # transformed_link_add = w3.toChecksumAddress(decize(link_add))
        transformed_link_add = i['args']['_link']
        link_contract = w3.eth.contract(transformed_link_add, abi=LINK_ABI)
        # 成功调用getLinkInfo()函数
        info['link_contract'] = transformed_link_add
        symbol_, token_, userA_, userB_, amountA_, amountB_, percentA_, totalPlan_, lockDays_, startTime_, status_, isAward_ = link_contract.caller.getLinkInfo()
        info['symbol_'] = symbol_
        info['token_'] = token_
        info['userA_'] = userA_
        info['userB_'] = userB_
        info['amountA_'] = amountA_
        info['amountB_'] = amountB_
        info['percentA_'] = percentA_
        info['totalPlan_'] = totalPlan_
        info['lockDays_'] = lockDays_
        info['startTime_'] = startTime_
        info['status_'] = status_
        info['isAward_'] = isAward_
        info_list.append(info)

    return transactionHash_list, info_list


def split_by_if_recorded(transactionHash_list, info_list, default_recent_transaction_hash_add):
    if transactionHash_list == []:
        # 没有交易记录：
        print('no transaction record')
        recorded = []
        unrecorded = []
    else:
        # 读取last_transaction_yesterday
        if os.path.exists(default_recent_transaction_hash_add):
            with open(default_recent_transaction_hash_add, 'r') as f:
                f = f.read()
            last_transaction_yesterday = f.strip()
        else:
            # 第一天，没有last_transaction_yesterday
            last_transaction_yesterday = None
        last_transaction_today = transactionHash_list[-1]
        with open(default_recent_transaction_hash_add, 'w') as f:
            f = f.write(last_transaction_today)

        # 第一天
        if not last_transaction_yesterday:
            recorded = []
            unrecorded = info_list
        else:
            # 正常情况
            # 已记录部分
            recorded_index = -1
            for index, i in enumerate(transactionHash_list):
                if i == last_transaction_yesterday:
                    recorded_index = index
            # log 记录各种特殊错误case
            # recorded:已记录部分
            # unrecorded:未记录部分
            recorded = info_list[:recorded_index + 1]
            if len(info_list) > recorded_index + 1:
                unrecorded = info_list[recorded_index + 1:]
            else:
                unrecorded = []

    return recorded, unrecorded
