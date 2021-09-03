from web3 import Web3
from web3.middleware import geth_poa_middleware
from Configs.eth.eth_config import PLEDGE_ABI, PLEDGE_ADDRESS, FACTORY_ABI, FACTORY_ADDRESS, LINK_ABI, LUCA_ADDRESS, \
    USDC_ADDRESS, IERC20_ABI, LUCA_USDC_ADDRESS, LUCA_DECIMALS, USDC_DECIMALS


class Web3Eth:

    def __init__(self, infura_url) -> None:
        self._w3 = Web3(Web3.HTTPProvider(infura_url))
        self._w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self._pledge_contract = self._w3.eth.contract(address=PLEDGE_ADDRESS, abi=PLEDGE_ABI)
        self._factory_contract = self._w3.eth.contract(address=FACTORY_ADDRESS, abi=FACTORY_ABI)
        self._luca_contract = self._w3.eth.contract(address=LUCA_ADDRESS, abi=IERC20_ABI)
        self._usdc_contract = self._w3.eth.contract(address=USDC_ADDRESS, abi=IERC20_ABI)

    def get_top11(self):
        res = self._pledge_contract.functions.queryNodeRank(start=1, end=11).call()
        print("top11： {}".format(res))
        return res

    def get_factory_link_active_events(self, from_block=0, to_block='latest'):
        events = self._factory_contract.events.LinkActive.getLogs(fromBlock=from_block, toBlock=to_block)
        return events

    def get_factory_link_created_events(self, from_block=0, to_block='latest'):
        events = self._factory_contract.events.LinkCreated.getLogs(fromBlock=from_block, toBlock=to_block)
        return events

    def get_block_by_number(self, block_number):
        block = self._w3.eth.get_block(block_number)
        return block

    def _get_link_contract(self, link_address):
        link_contract = self._w3.eth.contract(link_address, abi=LINK_ABI)
        return link_contract

    def get_link_info(self, link_address):
        link_contract = self._get_link_contract(link_address)
        symbol_, token_, userA_, userB_, amountA_, amountB_, percentA_, totalPlan_, lockDays_, startTime_, status_, isAward_ = link_contract.caller.getLinkInfo()
        link_info = LinkInfo(symbol_, token_, userA_, userB_, amountA_, amountB_, percentA_, totalPlan_, lockDays_,
                             startTime_, status_, isAward_)
        return link_info

    def get_link_close_info(self, link_address):
        link_contract = self._get_link_contract(link_address)
        closer_, startTime_, expiredTime_, closeTime_, closeReqA_, closeReqB_ = link_contract.caller.getCloseInfo()
        link_close_info = LinkCloseInfo(closer_, startTime_, expiredTime_, closeTime_, closeReqA_, closeReqB_)
        return link_close_info

    def get_luca_price(self):
        luca_balance = self._luca_contract.functions.balanceOf(LUCA_USDC_ADDRESS).call()
        usdc_balance = self._usdc_contract.functions.balanceOf(LUCA_USDC_ADDRESS).call()
        return (usdc_balance / 10 ** USDC_DECIMALS) / (luca_balance / 10 ** LUCA_DECIMALS)


class LinkInfo:

    def __init__(self, symbol_, token_, userA_, userB_, amountA_, amountB_, percentA_, totalPlan_, lockDays_,
                 startTime_, status_, isAward_):
        self.symbol_ = symbol_
        self.token_ = token_
        self.userA_ = userA_
        self.userB_ = userB_
        self.amountA_ = amountA_
        self.amountB_ = amountB_
        self.percentA_ = percentA_
        self.totalPlan_ = totalPlan_
        self.lockDays_ = lockDays_
        self.startTime_ = startTime_
        self.status_ = status_
        self.isAward_ = isAward_


class LinkCloseInfo:

    def __init__(self, closer_, startTime_, expiredTime_, closeTime_, closeReqA_, closeReqB_):
        self.closer_ = closer_
        self.startTime_ = startTime_
        self.expiredTime_ = expiredTime_
        self.closeTime_ = closeTime_
        self.closeReqA_ = closeReqA_
        self.closeReqB_ = closeReqB_
