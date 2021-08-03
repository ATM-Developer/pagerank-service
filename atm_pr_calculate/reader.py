import json
from web3 import Web3

with open('source_data.json', 'r') as f:
    source_data=json.load(f)

def prepare_data(source_data):
    pro_id = source_data['pro_id']
    factory_contract_address = source_data['factory_contract']

    w3 = Web3(Web3.HTTPProvider("https://rinkeby.infura.io/v3/{}".format(pro_id)))

    with open('factory.json') as j:
        factory_abi = json.load(j)
    with open('link.json') as j:
        link_abi = json.load(j)
        
    factory_contract = w3.eth.contract(factory_contract_address, abi=factory_abi)

    # hex-->dec
    def decize(hex):
        dec = '0x'+hex[26:]
        return dec

    # execute the filter
    _filter = factory_contract.events.LinkCreated.createFilter(fromBlock=0, toBlock='latest')
    transcation_list = _filter.get_all_entries()
    
    # prepare info for pg calculate
    info_list = []
    # prepare transactionHash_list for last_day record checking
    transactionHash_list = []
    for i in transcation_list:
        transactionHash_list.append(i['transactionHash'].hex())
        info = {}

        transformed_link_add = i['args']['_link']
        link_contract = w3.eth.contract(transformed_link_add, abi=link_abi)

        info['link_contract'] = transformed_link_add
        symbol_,token_,userA_,userB_,amountA_,amountB_,percentA_,totalPlan_,lockDays_,startTime_,status_,isAward_ = link_contract.caller.getLinkInfo()
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
        
    return transactionHash_list,info_list
        
